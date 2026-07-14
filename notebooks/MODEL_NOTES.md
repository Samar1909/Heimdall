# model.ipynb — Model Notes

## Source data

Two files, `data/creditcardTrain.csv` (~1.3M rows, Jan 2019 - Jun 2020) and
`data/creditcardTest.csv` (~556K rows, Jun-Dec 2020), from the Sparkov
simulated credit-card transaction dataset. ~0.4% of rows are fraud in each
file. Original columns:

`Unnamed: 0, trans_date_trans_time, cc_num, merchant, category, amt, first,
last, gender, street, city, state, zip, lat, long, city_pop, job, dob,
trans_num, unix_time, merch_lat, merch_long, is_fraud`

## Columns removed

- `Unnamed: 0` — a row index carried over from the CSV export, no signal.
- `first`, `last` — cardholder name, no predictive value and pure PII.
- `street` — free-text address; `city`/`state`/`zip`/`lat`/`long` already
  capture location.
- `city`, `zip` — city has ~900 unique values (too sparse to encode usefully)
  and zip is redundant with `lat`/`long`/`state`, which capture the same
  location more usably for a tree model.
- `trans_num` — a random per-transaction hash id, no signal.
- `dob`, `trans_date_trans_time` — consumed to derive `age`, `hour`,
  `day_of_week`, `month` (below), then dropped since the raw timestamp/date
  of birth themselves aren't usable model inputs.
- `lat`, `long`, `merch_lat`, `merch_long` — consumed to derive `distance_km`
  (below), then dropped. Keeping raw coordinates risks the model keying off
  specific cities/neighborhoods instead of the actual fraud signal (distance
  from the cardholder's home location), which wouldn't generalize.
- `merchant`, `job`, `state` — dropped after being frequency-encoded (below);
  the raw string columns aren't usable directly by XGBoost.
- `cc_num` — dropped after being used to group transactions per card for the
  behavioral features (below); the raw card number itself carries no
  generalizable signal.

## Columns created

- **`age`** — years between `dob` and `trans_date_trans_time`. Fraud rates
  vary by cardholder age group in this dataset.
- **`hour`**, **`day_of_week`**, **`month`** — extracted from
  `trans_date_trans_time`. Fraud is not uniformly distributed across time of
  day / week / year.
- **`distance_km`** — haversine distance between the cardholder's location
  (`lat`/`long`) and the merchant's location (`merch_lat`/`merch_long`).
  Fraudulent transactions tend to occur unusually far from the cardholder's
  home location, making this one of the strongest engineered signals in this
  dataset.
- **`gender`** — binary-encoded (`1` = male, `0` = female) from the original
  `M`/`F` string.
- **`category`** — one-hot encoded (14 categories: `grocery_pos`,
  `shopping_net`, `misc_net`, etc.) since it's a small, fixed set of
  merchant-category values.
- **`merchant_freq`**, **`job_freq`**, **`state_freq`** — frequency encoding
  (each value replaced by its relative frequency in the training set) for
  `merchant` (693 unique values), `job` (478), and `state` (50) — too
  high-cardinality to one-hot without exploding the feature space. The
  frequency map is fit on the training set only and applied to the test set,
  so unseen categories map to `0` and no test-set category distribution
  leaks into training.
- **`card_tx_count`**, **`card_avg_amt_prior`**, **`amt_to_avg_ratio`** — a
  per-card behavioral profile: for each transaction, how many transactions
  this card has made before it, the average amount of those prior
  transactions, and the ratio of the current amount to that average. These
  are computed causally — sorting each card's transactions by time and using
  `shift(1).expanding()` so a row only ever sees that card's *past*
  transactions, never its own or a future one. This mirrors the intended
  production design: recompute a cardholder's behavioral profile from their
  transaction history before scoring a new transaction. The `train`/`test`
  files are concatenated before this step so a card's history correctly
  carries over from the training period into the test period, rather than
  resetting to zero at the test file's start.

## Model choice: XGBoost

Gradient-boosted trees are a strong default for this kind of problem:
tabular data with a mix of numeric and encoded categorical features, a
highly imbalanced target (~0.4% fraud), and a need for the resulting model
to stay explainable (via SHAP `TreeExplainer`, used elsewhere in this repo's
API). XGBoost specifically handles the class imbalance directly through
`scale_pos_weight` rather than requiring manual resampling.

## Why `logloss` as the eval metric

`logloss` rewards well-calibrated probabilities and keeps discriminating
between training rounds even once a model is already fitting the class
imbalance reasonably well. Metrics like `aucpr` can plateau near their
maximum value early once the ranking of predictions stabilizes, even though
the underlying probabilities (and the model) are still improving — which
would make early stopping trigger prematurely on noise rather than a real
lack of progress.

## Hyperparameters

```python
ratio = (y_train == 0).sum() / (y_train == 1).sum()

clf_xgb = xgb.XGBClassifier(
    objective='binary:logistic',
    eval_metric='logloss',
    early_stopping_rounds=50,
    scale_pos_weight=ratio,
    learning_rate=0.03,
    n_estimators=1000,
    max_depth=6,
    min_child_weight=5,
    subsample=0.8,
    colsample_bytree=0.8,
    seed=42,
)
```

| Param | Value | Why |
|---|---|---|
| `scale_pos_weight` | ratio of legit:fraud rows in `y_train` | Directly compensates for the ~250:1 class imbalance by upweighting the minority (fraud) class's gradient, instead of the model defaulting to "always predict legit". |
| `early_stopping_rounds` | `50` | Stops training once validation `logloss` hasn't improved for 50 consecutive rounds — long enough that a temporary plateau isn't mistaken for convergence, short enough to still save unnecessary computation once the model is genuinely done learning. |
| `learning_rate` | `0.03` | A low shrinkage rate means each tree only contributes a small correction, so the ensemble needs many rounds and spreads what it learns across the full forest rather than a handful of trees — this makes the model less sensitive to any single split and more robust to noise in individual features. |
| `n_estimators` | `1000` | Sets a generous ceiling on the number of trees `early_stopping_rounds` is allowed to grow into, given the low `learning_rate`. |
| `max_depth` | `6` | Lets each tree capture interactions between a handful of features (e.g. `distance_km` combined with `hour` and `category`) without growing deep enough to memorize individual rows. |
| `min_child_weight` | `5` | Requires a leaf to cover a minimum amount of (weighted) training data before a split is accepted, preventing the model from carving out tiny leaves around a handful of examples. |
| `subsample` | `0.8` | Each tree trains on a random 80% sample of rows, adding randomness across the ensemble so no single tree can fit all of the available signal at once. |
| `colsample_bytree` | `0.8` | Each tree only considers a random 80% of features, for the same reason — spreading reliance across features like `distance_km`, `amt_to_avg_ratio`, and the frequency-encoded columns instead of overusing any one of them. |

## Performance

Training used all `n_estimators=1000` rounds — `best_iteration=999`, i.e.
early stopping never triggered, meaning validation `logloss` was still
(slowly) improving at the final round rather than plateauing. Validation
`logloss` decreased smoothly from ~0.67 at round 0 to ~0.007 by round 999,
with no sudden collapse to a small number of trees.

Confusion matrix on the full `creditcardTest.csv` (556K rows, 2,145 fraud
transactions):

| | Predicted Legit | Predicted Fraud |
|---|---|---|
| **Legit** | 552,680 | 894 |
| **Fraud** | 327 | 1,818 |

That's **~85% recall** (1,818 of 2,145 fraud transactions caught) and **~67%
precision** (1,818 of 2,712 flagged transactions were actually fraud) on the
fraud class.
