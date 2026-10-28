"""Leakage-aware late-delivery classification for the Olist portfolio project."""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .quality import normalize_sources, read_sources


CATEGORICAL_FEATURES = [
    "customer_state",
    "dominant_seller_state",
    "dominant_category",
    "dominant_payment_type",
    "purchase_month",
    "purchase_weekday",
]

NUMERIC_FEATURES = [
    "purchase_hour",
    "approval_wait_minutes",
    "promise_lead_days",
    "item_count",
    "seller_count",
    "category_count",
    "seller_state_count",
    "same_state_item_share",
    "product_total_brl",
    "freight_total_brl",
    "mean_item_price_brl",
    "mean_item_freight_brl",
    "freight_to_products_ratio",
    "payment_count",
    "installments_max",
    "installments_mean",
]

FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET_DEFINITION = (
    "1 quando a data de entrega ao cliente é posterior à data estimada, "
    "comparando dias de calendário; 0 nos demais pedidos elegíveis."
)
TRAIN_CUTOFF = pd.Timestamp("2018-01-01")
VALIDATION_CUTOFF = pd.Timestamp("2018-07-01")
RANDOM_STATE = 42


def _dominant_value_by_order(frame: pd.DataFrame, column: str, output_name: str) -> pd.Series:
    """Choose the most frequent value per order, breaking ties lexicographically."""
    values = frame[["order_id", column]].copy()
    values[column] = values[column].astype("string").fillna("UNKNOWN")
    counts = values.groupby(["order_id", column], dropna=False, observed=True).size().rename("_count").reset_index()
    counts = counts.sort_values(
        ["order_id", "_count", column], ascending=[True, False, True], kind="stable",
    )
    return counts.drop_duplicates("order_id").set_index("order_id")[column].rename(output_name)


def build_model_dataset(sources: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.Series, pd.Series, dict]:
    """Build one row per eligible delivered order using approval-time features only."""
    orders = sources["orders"].copy()
    customers = sources["customers"][["customer_id", "customer_state"]].copy()
    items = sources["items"].copy()
    payments = sources["payments"].copy()
    products = sources["products"][["product_id", "product_category_name"]].copy()
    categories = sources["categories"][["product_category_name", "product_category_name_english"]].copy()
    sellers = sources["sellers"][["seller_id", "seller_state"]].copy()

    category_lookup = products.merge(
        categories, on="product_category_name", how="left", validate="many_to_one",
    )
    category_lookup["model_category"] = (
        category_lookup["product_category_name_english"]
        .fillna(category_lookup["product_category_name"])
        .fillna("UNKNOWN")
        .astype("string")
    )

    item_rows = items.merge(
        category_lookup[["product_id", "model_category"]],
        on="product_id", how="left", validate="many_to_one",
    )
    item_rows = item_rows.merge(
        orders[["order_id", "customer_id"]], on="order_id", how="left", validate="many_to_one",
    )
    item_rows = item_rows.merge(
        customers, on="customer_id", how="left", validate="many_to_one",
    )
    item_rows = item_rows.merge(
        sellers[["seller_id", "seller_state"]], on="seller_id", how="left", validate="many_to_one",
    )
    item_rows["model_category"] = item_rows["model_category"].fillna("UNKNOWN").astype("string")
    item_rows["seller_state"] = item_rows["seller_state"].fillna("UNKNOWN").astype("string")
    item_rows["same_state_item"] = item_rows["customer_state"].eq(item_rows["seller_state"]).astype(float)

    item_features = item_rows.groupby("order_id", sort=False).agg(
        item_count=("order_item_id", "size"),
        seller_count=("seller_id", "nunique"),
        category_count=("model_category", "nunique"),
        seller_state_count=("seller_state", "nunique"),
        product_total_cents=("price_cents", "sum"),
        freight_total_cents=("freight_value_cents", "sum"),
        mean_item_price_cents=("price_cents", "mean"),
        mean_item_freight_cents=("freight_value_cents", "mean"),
        same_state_item_share=("same_state_item", "mean"),
    )
    item_features = item_features.join(
        _dominant_value_by_order(item_rows, "model_category", "dominant_category")
    ).join(
        _dominant_value_by_order(item_rows, "seller_state", "dominant_seller_state")
    )

    payment_features = payments.groupby("order_id", sort=False).agg(
        payment_count=("payment_sequential", "size"),
        installments_max=("payment_installments", "max"),
        installments_mean=("payment_installments", "mean"),
    )
    payment_features = payment_features.join(
        _dominant_value_by_order(payments, "payment_type", "dominant_payment_type")
    )

    model_frame = orders.merge(customers, on="customer_id", how="left", validate="many_to_one")
    model_frame = model_frame.join(item_features, on="order_id").join(payment_features, on="order_id")

    purchase = model_frame["order_purchase_timestamp"]
    delivered = model_frame["order_delivered_customer_date"]
    estimated = model_frame["order_estimated_delivery_date"]
    eligible = (
        model_frame["order_status"].eq("delivered")
        & purchase.notna()
        & delivered.notna()
        & estimated.notna()
        & delivered.ge(purchase)
        & estimated.dt.normalize().ge(purchase.dt.normalize())
    )

    labeled = model_frame.loc[eligible].copy()
    purchase = labeled["order_purchase_timestamp"]
    approved = labeled["order_approved_at"]
    delivered = labeled["order_delivered_customer_date"]
    estimated = labeled["order_estimated_delivery_date"]

    y = delivered.dt.normalize().gt(estimated.dt.normalize()).astype("int8").rename("delivered_late")
    labeled["purchase_hour"] = purchase.dt.hour.astype(float)
    labeled["purchase_month"] = purchase.dt.month.astype("string")
    labeled["purchase_weekday"] = purchase.dt.dayofweek.astype("string")
    approval_wait = (approved - purchase).dt.total_seconds().div(60)
    labeled["approval_wait_minutes"] = approval_wait.where(approval_wait.ge(0))
    labeled["promise_lead_days"] = (
        estimated.dt.normalize() - purchase.dt.normalize()
    ).dt.total_seconds().div(86400)
    labeled["product_total_brl"] = labeled["product_total_cents"].astype("Float64") / 100
    labeled["freight_total_brl"] = labeled["freight_total_cents"].astype("Float64") / 100
    labeled["mean_item_price_brl"] = labeled["mean_item_price_cents"].astype("Float64") / 100
    labeled["mean_item_freight_brl"] = labeled["mean_item_freight_cents"].astype("Float64") / 100
    labeled["freight_to_products_ratio"] = (
        labeled["freight_total_brl"]
        / labeled["product_total_brl"].where(labeled["product_total_brl"].gt(0))
    )

    X = labeled[FEATURES].copy()
    for column in CATEGORICAL_FEATURES:
        X[column] = X[column].astype(object).where(X[column].notna(), np.nan)
    for column in NUMERIC_FEATURES:
        X[column] = pd.to_numeric(X[column], errors="coerce").astype(float)
    purchase_time = purchase.reset_index(drop=True).rename("purchase_timestamp")
    X = X.reset_index(drop=True)
    y = y.reset_index(drop=True)

    details = {
        "source_orders": int(len(orders)),
        "eligible_labeled_orders": int(len(labeled)),
        "excluded_delivered_orders": int(model_frame["order_status"].eq("delivered").sum() - len(labeled)),
        "late_orders": int(y.sum()),
        "late_rate": float(y.mean()),
    }
    return X, y, purchase_time, details


def _make_preprocessor(ColumnTransformer, Pipeline, SimpleImputer, OneHotEncoder, StandardScaler):
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(
            handle_unknown="ignore", min_frequency=20, sparse_output=False,
        )),
    ])
    return ColumnTransformer(
        [("numeric", numeric, NUMERIC_FEATURES), ("categorical", categorical, CATEGORICAL_FEATURES)],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def _top_fraction_metrics(y_true: np.ndarray, probabilities: np.ndarray, fraction: float = 0.10) -> dict:
    count = max(1, int(math.ceil(len(probabilities) * fraction)))
    selected = np.argsort(-probabilities, kind="stable")[:count]
    actual = y_true[selected]
    prevalence = float(np.mean(y_true))
    precision = float(np.mean(actual)) if len(actual) else 0.0
    positives = int(np.sum(y_true))
    recall = float(np.sum(actual) / positives) if positives else 0.0
    return {
        "capacity_fraction": fraction,
        "orders_flagged": int(count),
        "precision": precision,
        "recall": recall,
        "lift": float(precision / prevalence) if prevalence else 0.0,
    }


def _choose_f1_threshold(y_true: np.ndarray, probabilities: np.ndarray, precision_recall_curve) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, probabilities)
    if not len(thresholds):
        return 0.5
    denominator = precision[:-1] + recall[:-1]
    f1 = np.divide(
        2 * precision[:-1] * recall[:-1], denominator,
        out=np.zeros_like(denominator), where=denominator > 0,
    )
    return float(thresholds[int(np.argmax(f1))])


def _evaluate(y_true: np.ndarray, probabilities: np.ndarray, threshold: float, metrics_module: dict) -> dict:
    predictions = probabilities >= threshold
    y_true_int = y_true.astype(int)
    return {
        "average_precision": float(metrics_module["average_precision_score"](y_true_int, probabilities)),
        "roc_auc": float(metrics_module["roc_auc_score"](y_true_int, probabilities)),
        "brier_score": float(metrics_module["brier_score_loss"](y_true_int, probabilities)),
        "threshold": float(threshold),
        "precision_at_threshold": float(metrics_module["precision_score"](y_true_int, predictions, zero_division=0)),
        "recall_at_threshold": float(metrics_module["recall_score"](y_true_int, predictions, zero_division=0)),
        "f1_at_threshold": float(metrics_module["f1_score"](y_true_int, predictions, zero_division=0)),
        "top_10_percent": _top_fraction_metrics(y_true_int, probabilities),
        "prevalence": float(np.mean(y_true_int)),
    }


def _save_evaluation_plots(output_dir: Path, y_test: np.ndarray, probabilities: np.ndarray, precision_recall_curve, calibration_curve) -> None:
    precision, recall, _ = precision_recall_curve(y_test, probabilities)
    prevalence = float(np.mean(y_test))
    fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")
    ax.step(recall, precision, where="post", color="#176b87", linewidth=2, label="Modelo no teste")
    ax.axhline(prevalence, color="#7b8794", linestyle="--", label=f"Referência sem habilidade ({prevalence:.1%})")
    ax.set(xlabel="Recall", ylabel="Precisão", title="Curva precisão-recall — período de teste")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    fig.savefig(output_dir / "precision_recall.png", dpi=150, facecolor="white")
    plt.close(fig)

    observed, predicted = calibration_curve(y_test, probabilities, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(8, 5), layout="constrained")
    ax.plot([0, 1], [0, 1], color="#7b8794", linestyle="--", label="Calibração perfeita")
    ax.plot(predicted, observed, marker="o", color="#176b87", linewidth=2, label="Modelo no teste")
    ax.set(xlabel="Risco previsto médio", ylabel="Frequência observada", title="Calibração das probabilidades — teste")
    ax.set_xlim(0, max(0.2, float(np.max(predicted)) * 1.1))
    ax.set_ylim(0, max(0.2, float(np.max(observed)) * 1.1))
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    fig.savefig(output_dir / "calibration.png", dpi=150, facecolor="white")
    plt.close(fig)


def train_delay_model(raw_dir: Path, output_dir: Path, model_path: Path) -> dict:
    """Train candidates, select on validation, and report once on a later holdout."""
    try:
        from joblib import dump
        from sklearn.calibration import calibration_curve
        from sklearn.compose import ColumnTransformer
        from sklearn.dummy import DummyClassifier
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.inspection import permutation_importance
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import (
            average_precision_score,
            brier_score_loss,
            f1_score,
            precision_recall_curve,
            precision_score,
            recall_score,
            roc_auc_score,
        )
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
    except ImportError as error:
        raise RuntimeError('Instale as dependências de ML com: python -m pip install -e ".[ml]"') from error

    raw_dir, output_dir, model_path = Path(raw_dir), Path(output_dir), Path(model_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path.parent.mkdir(parents=True, exist_ok=True)

    raw_frames, source_manifest = read_sources(raw_dir)
    sources, quality_issues = normalize_sources(raw_frames)
    X, y, purchase_time, dataset_details = build_model_dataset(sources)

    train_mask = purchase_time < TRAIN_CUTOFF
    validation_mask = (purchase_time >= TRAIN_CUTOFF) & (purchase_time < VALIDATION_CUTOFF)
    test_mask = purchase_time >= VALIDATION_CUTOFF
    masks = {"train": train_mask, "validation": validation_mask, "test": test_mask}
    for split_name, mask in masks.items():
        if not bool(mask.any()):
            raise ValueError(f"A janela temporal {split_name} não contém pedidos elegíveis.")
        if y.loc[mask].nunique() < 2:
            raise ValueError(f"A janela temporal {split_name} precisa conter as duas classes.")

    X_train, y_train = X.loc[train_mask], y.loc[train_mask]
    X_validation, y_validation = X.loc[validation_mask], y.loc[validation_mask]
    X_test, y_test = X.loc[test_mask], y.loc[test_mask]
    y_train_np = y_train.to_numpy(dtype=int)
    y_validation_np = y_validation.to_numpy(dtype=int)
    y_test_np = y_test.to_numpy(dtype=int)

    preprocess = _make_preprocessor(ColumnTransformer, Pipeline, SimpleImputer, OneHotEncoder, StandardScaler)
    candidates = {
        "logistic_regression": Pipeline([
            ("preprocess", preprocess),
            ("model", LogisticRegression(max_iter=2000, solver="lbfgs", random_state=RANDOM_STATE)),
        ]),
        "hist_gradient_boosting": Pipeline([
            ("preprocess", _make_preprocessor(ColumnTransformer, Pipeline, SimpleImputer, OneHotEncoder, StandardScaler)),
            ("model", HistGradientBoostingClassifier(
                learning_rate=0.06,
                max_iter=160,
                max_leaf_nodes=15,
                min_samples_leaf=35,
                l2_regularization=1.0,
                early_stopping=False,
                random_state=RANDOM_STATE,
            )),
        ]),
    }
    prior = DummyClassifier(strategy="prior")
    prior.fit(X_train, y_train_np)
    prior_validation = prior.predict_proba(X_validation)[:, 1]
    prior_test = prior.predict_proba(X_test)[:, 1]

    validation_scores = {}
    for name, estimator in candidates.items():
        estimator.fit(X_train, y_train_np)
        validation_scores[name] = float(average_precision_score(y_validation_np, estimator.predict_proba(X_validation)[:, 1]))

    selected_name = max(validation_scores, key=validation_scores.get)
    selected_model = candidates[selected_name]
    validation_probabilities = selected_model.predict_proba(X_validation)[:, 1]
    threshold = _choose_f1_threshold(y_validation_np, validation_probabilities, precision_recall_curve)
    test_probabilities = selected_model.predict_proba(X_test)[:, 1]

    metrics_module = {
        "average_precision_score": average_precision_score,
        "roc_auc_score": roc_auc_score,
        "brier_score_loss": brier_score_loss,
        "precision_score": precision_score,
        "recall_score": recall_score,
        "f1_score": f1_score,
    }
    selected_metrics = _evaluate(y_test_np, test_probabilities, threshold, metrics_module)
    prior_metrics = {
        "average_precision": float(average_precision_score(y_test_np, prior_test)),
        "roc_auc": float(roc_auc_score(y_test_np, prior_test)),
        "brier_score": float(brier_score_loss(y_test_np, prior_test)),
        "prevalence": float(np.mean(y_test_np)),
    }
    prior_validation_metrics = _evaluate(y_validation_np, prior_validation, 0.5, metrics_module)

    model_selection = pd.DataFrame([
        {"candidate": name, "validation_average_precision": score}
        for name, score in validation_scores.items()
    ]).sort_values("validation_average_precision", ascending=False)
    model_selection.to_csv(output_dir / "model_selection.csv", index=False)

    sample_count = min(3000, len(X_validation))
    X_explain = X_validation.sample(n=sample_count, random_state=RANDOM_STATE)
    y_explain = y_validation.loc[X_explain.index]
    importance = permutation_importance(
        selected_model,
        X_explain,
        y_explain.to_numpy(dtype=int),
        n_repeats=3,
        random_state=RANDOM_STATE,
        scoring="average_precision",
        n_jobs=2,
    )
    importance_frame = pd.DataFrame({
        "feature": X.columns,
        "average_precision_decrease": importance.importances_mean,
        "standard_deviation": importance.importances_std,
    }).sort_values("average_precision_decrease", ascending=False)
    importance_frame.to_csv(output_dir / "feature_importance.csv", index=False)

    _save_evaluation_plots(output_dir, y_test_np, test_probabilities, precision_recall_curve, calibration_curve)
    metrics = {
        "project": "Olist Delivery Risk",
        "target": TARGET_DEFINITION,
        "prediction_time": "Após aprovação do pedido; somente atributos disponíveis nesse momento entram no modelo.",
        "source_period": {
            "purchase_start": str(purchase_time.min().date()),
            "purchase_end": str(purchase_time.max().date()),
        },
        "cutoffs": {
            "train_before": str(TRAIN_CUTOFF.date()),
            "validation_from": str(TRAIN_CUTOFF.date()),
            "validation_before": str(VALIDATION_CUTOFF.date()),
            "test_from": str(VALIDATION_CUTOFF.date()),
        },
        "dataset": dataset_details,
        "splits": {
            name: {
                "orders": int(mask.sum()),
                "late_orders": int(y.loc[mask].sum()),
                "late_rate": float(y.loc[mask].mean()),
            }
            for name, mask in masks.items()
        },
        "model_selection": {
            "criterion": "Maior average precision na validação temporal.",
            "validation_average_precision": validation_scores,
            "selected_model": selected_name,
            "validation_threshold_maximizing_f1": threshold,
        },
        "temporal_shift": {
            "validation_late_rate": float(y_validation_np.mean()),
            "test_late_rate": float(y_test_np.mean()),
            "late_rate_change_percentage_points": float((y_test_np.mean() - y_validation_np.mean()) * 100),
            "validation_average_precision": float(validation_scores[selected_name]),
            "test_average_precision": float(selected_metrics["average_precision"]),
        },
        "test": {
            "selected_model": selected_metrics,
            "prior_baseline": prior_metrics,
            "no_skill_average_precision": float(y_test_np.mean()),
            "prior_baseline_validation_average_precision": prior_validation_metrics["average_precision"],
        },
        "features": {
            "categorical": CATEGORICAL_FEATURES,
            "numeric": NUMERIC_FEATURES,
            "excluded_examples": [
                "order_id, customer_id e seller_id",
                "data de despacho e data de entrega reais",
                "avaliação do cliente e demais resultados posteriores à aprovação",
            ],
        },
        "quality_warning_count": len(quality_issues),
        "source_hashes": {name: value["sha256"] for name, value in source_manifest.items()},
        "limitations": [
            "A base contém pedidos históricos de 2016–2018 e não representa a operação atual da Olist.",
            "O alvo é definido somente para pedidos entregues com datas coerentes; cancelamentos ficam fora.",
            "O teste temporal mede generalização para uma janela posterior desta mesma base, não valida implantação atual.",
            "O limiar baseado em F1 não estima impacto financeiro ou capacidade operacional.",
        ],
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8",
    )

    feature_labels = {
        "customer_state": "Estado do cliente",
        "promise_lead_days": "Prazo prometido (dias)",
        "same_state_item_share": "Itens no mesmo estado (%)",
        "installments_mean": "Parcelas médias",
        "dominant_seller_state": "Estado do vendedor predominante",
        "mean_item_freight_brl": "Frete médio por item (R$)",
        "mean_item_price_brl": "Preço médio por item (R$)",
        "installments_max": "Parcelas máximas",
        "approval_wait_minutes": "Minutos até aprovação",
        "seller_count": "Número de vendedores",
        "product_total_brl": "Valor total dos produtos (R$)",
        "freight_to_products_ratio": "Frete / produtos",
        "payment_count": "Número de pagamentos",
        "purchase_hour": "Hora da compra",
    }
    top_features = importance_frame.head(10).sort_values("average_precision_decrease").copy()
    top_features["label"] = top_features["feature"].map(feature_labels).fillna(top_features["feature"])
    fig, ax = plt.subplots(figsize=(9, 5.5), layout="constrained")
    colors = ["#176b87" if value >= 0 else "#bd6b4b" for value in top_features["average_precision_decrease"]]
    ax.barh(top_features["label"], top_features["average_precision_decrease"], color=colors)
    ax.axvline(0, color="#7b8794", linewidth=0.8)
    ax.set(xlabel="Queda média de PR-AUC ao embaralhar a variável", title="Importância por permutação — validação")
    ax.grid(axis="x", alpha=0.2)
    ax.set_axisbelow(True)
    fig.savefig(output_dir / "permutation_importance.png", dpi=150, facecolor="white")
    plt.close(fig)

    eligible_count_pt = f"{dataset_details['eligible_labeled_orders']:,}".replace(",", ".")
    late_count_pt = f"{dataset_details['late_orders']:,}".replace(",", ".")
    late_rate_pt = f"{dataset_details['late_rate']:.2%}".replace(".", ",")
    validation_rate_pt = f"{float(y_validation_np.mean()):.2%}".replace(".", ",")
    test_rate_pt = f"{float(y_test_np.mean()):.2%}".replace(".", ",")
    model_card = f"""# Olist Delivery Risk — cartão do modelo

## Objetivo

Estimar o risco de atraso de um pedido após a aprovação, para priorizar análise e eventual contato proativo. O painel é uma demonstração histórica de portfólio, não uma ferramenta operacional da Olist.

## Alvo e população

{TARGET_DEFINITION}

O conjunto rotulado contém {eligible_count_pt} pedidos entregues elegíveis, dos quais {late_count_pt} atrasaram ({late_rate_pt}). Pedidos cancelados, não entregues e entregues sem datas coerentes não recebem rótulo neste estudo.

## Desenho de validação

- Treino: compras anteriores a {TRAIN_CUTOFF.date()}.
- Validação: compras de {TRAIN_CUTOFF.date()} a {VALIDATION_CUTOFF.date() - pd.Timedelta(days=1)}.
- Teste final: compras a partir de {VALIDATION_CUTOFF.date()}.
- O candidato foi escolhido por PR-AUC na validação temporal; o limiar que maximiza F1 também foi escolhido na validação. O teste não participa dessas escolhas.

## Resultado no teste

- Modelo selecionado: `{selected_name}`.
- PR-AUC: {selected_metrics['average_precision']:.4f}; referência sem habilidade: {selected_metrics['prevalence']:.4f}.
- ROC-AUC: {selected_metrics['roc_auc']:.4f}.
- Brier score: {selected_metrics['brier_score']:.4f} (menor é melhor para a calibração probabilística).
- Brier do baseline de prevalência: {prior_metrics['brier_score']:.4f}; a melhora absoluta é pequena.
- Precisão nos 10% de maior risco: {selected_metrics['top_10_percent']['precision']:.2%}; recall: {selected_metrics['top_10_percent']['recall']:.2%}; lift: {selected_metrics['top_10_percent']['lift']:.2f}×.

Na validação, a taxa de atraso foi {validation_rate_pt} e a PR-AUC foi {validation_scores[selected_name]:.4f}. No teste, a prevalência caiu para {test_rate_pt} e a PR-AUC foi {selected_metrics['average_precision']:.4f}. Essa mudança temporal limita a estabilidade do modelo. A curva de calibração também mostra excesso de previsão no grupo de maior risco.

## Prevenção de vazamento

O modelo não recebe identificadores de pedido/cliente/vendedor, avaliações, data real de despacho ou data real de entrega. Usa somente atributos de compra, pagamento, destino, itens e prazo estimado que estão disponíveis até a aprovação.

## Limitações

Os dados cobrem 2016–2018. Mudanças em transportadoras, catálogo, regiões, prazos e comportamento de compra podem invalidar o desempenho. A avaliação não prova causalidade, economia, nem validade para a operação atual. A população de treino inclui apenas pedidos entregues e elegíveis.

## Artefatos

- `metrics.json`: métricas, janelas e hashes das fontes.
- `model_selection.csv`: comparação dos candidatos na validação.
- `feature_importance.csv` e `permutation_importance.png`: interpretação por permutação, calculada na validação.
- `precision_recall.png` e `calibration.png`: diagnóstico no teste final.
- O pipeline serializado fica no caminho local configurado e não é publicado junto aos dados brutos.
"""
    (output_dir / "model_card.md").write_text(model_card, encoding="utf-8")

    fitted_encoder = (
        selected_model.named_steps["preprocess"]
        .named_transformers_["categorical"]
        .named_steps["onehot"]
    )
    categorical_values = {
        feature: [str(value) for value in values]
        for feature, values in zip(CATEGORICAL_FEATURES, fitted_encoder.categories_)
    }
    artifact = {
        "pipeline": selected_model,
        "features": FEATURES,
        "categorical_values": categorical_values,
        "threshold": threshold,
        "selected_model": selected_name,
        "prediction_time": "after_order_approval",
        "training_cutoff": str(TRAIN_CUTOFF.date()),
        "validation_cutoff": str(VALIDATION_CUTOFF.date()),
    }
    dump(artifact, model_path, compress=3)
    return {
        "selected_model": selected_name,
        "test_average_precision": selected_metrics["average_precision"],
        "test_baseline_average_precision": selected_metrics["prevalence"],
        "test_top_10_percent_precision": selected_metrics["top_10_percent"]["precision"],
        "test_top_10_percent_recall": selected_metrics["top_10_percent"]["recall"],
        "metrics_path": str(output_dir / "metrics.json"),
        "model_card_path": str(output_dir / "model_card.md"),
        "model_path": str(model_path),
    }
