import streamlit as st

from regulatory_engine.application import (
    evaluate_import,
)
from regulatory_engine.models import (
    ImportRequest,
)


st.set_page_config(
    page_title="Analyse réglementaire import",
    page_icon="📦",
    layout="wide",
)


def format_money(value):
    if value is None:
        return "—"

    return f"{value:,.2f} €"


def format_rate(value):
    if value is None:
        return "—"

    return f"{value:g} %"


def render_classification(result):
    classification = result[
        "classification"
    ]

    st.subheader(
        "Classification douanière"
    )

    col1, col2 = st.columns(2)

    col1.metric(
        "Code NC",
        classification.get(
            "nc_code"
        )
        or "Non déterminé",
    )

    col2.metric(
        "Statut",
        classification.get(
            "status",
            "—",
        ),
    )

    reason = classification.get(
        "reason"
    )

    if reason:
        st.write(
            reason
        )

    missing_information = (
        classification.get(
            "missing_information"
        )
        or []
    )

    if missing_information:
        st.warning(
            "Informations supplémentaires requises : "
            + ", ".join(
                missing_information
            )
        )


def render_standard_tariff(result):
    tariff = result.get(
        "tariff"
    )

    st.subheader(
        "Droits de douane standard"
    )

    if not tariff:
        st.info(
            "Le droit de douane standard "
            "n'a pas pu être déterminé."
        )
        return

    col1, col2 = st.columns(2)

    col1.metric(
        "Taux standard",
        format_rate(
            tariff.get(
                "standard_rate_pct"
            )
        ),
    )

    col2.metric(
        "Droit estimé",
        format_money(
            tariff.get(
                "standard_duty_eur"
            )
        ),
    )

    calculation_basis = tariff.get(
        "calculation_basis"
    )

    if calculation_basis:
        st.caption(
            f"Calcul : {calculation_basis}"
        )


def render_preference(result):
    preference = result.get(
        "preferential_tariff"
    )

    st.subheader(
        "Accord commercial"
    )

    if not preference:
        st.info(
            "Aucune préférence tarifaire "
            "n'a été évaluée."
        )
        return

    agreement = (
        preference.get(
            "agreement"
        )
        or {}
    )

    if not agreement:
        st.info(
            "Aucun accord commercial pris "
            "en charge par le corpus."
        )
        return

    st.write(
        f"**Accord :** "
        f"{agreement.get('agreement_name', '—')}"
    )

    st.write(
        f"**Statut :** "
        f"{preference.get('status', '—')}"
    )

    col1, col2, col3 = st.columns(
        3
    )

    col1.metric(
        "Taux préférentiel",
        format_rate(
            preference.get(
                "preferential_rate_pct"
            )
        ),
    )

    col2.metric(
        "Droit préférentiel",
        format_money(
            preference.get(
                "preferential_duty_eur"
            )
        ),
    )

    col3.metric(
        "Économie potentielle",
        format_money(
            preference.get(
                "saving_eur"
            )
        ),
    )

    render_origin(
        preference
    )

    render_sources(
        preference
    )


def render_origin(preference):
    origin_verification = (
        preference.get(
            "origin_verification"
        )
        or {}
    )

    origin_rule = (
        preference.get(
            "origin_rule"
        )
        or {}
    )

    if not origin_verification:
        return

    st.markdown(
        "#### Origine préférentielle"
    )

    status = origin_verification.get(
        "status"
    )

    if status == "NOT_VERIFIED":
        st.warning(
            origin_verification.get(
                "reason",
                (
                    "L'origine préférentielle "
                    "n'est pas vérifiée."
                ),
            )
        )
    else:
        st.write(
            status
        )

    if origin_rule:
        with st.expander(
            "Voir la règle d'origine"
        ):
            st.write(
                origin_rule.get(
                    "rule_text",
                    "—",
                )
            )

            if origin_rule.get(
                "hs_code"
            ):
                st.caption(
                    f"HS4 : "
                    f"{origin_rule['hs_code']}"
                )


def render_sources(preference):
    legal_basis = (
        preference.get(
            "legal_basis"
        )
        or []
    )

    origin_rule = (
        preference.get(
            "origin_rule"
        )
        or {}
    )

    tariff_schedule = (
        preference.get(
            "tariff_schedule"
        )
        or {}
    )

    if not (
        legal_basis
        or origin_rule
        or tariff_schedule
    ):
        return

    st.subheader(
        "Sources"
    )

    for provision in legal_basis:
        title = (
            f"{provision.get('source_document', 'Document')}"
            f" — Article "
            f"{provision.get('article', '—')}"
        )

        with st.expander(
            title
        ):
            st.write(
                provision.get(
                    "source_excerpt"
                )
                or provision.get(
                    "text"
                )
                or "—"
            )

            if provision.get(
                "source_page"
            ):
                st.caption(
                    f"Page "
                    f"{provision['source_page']}"
                )

    if origin_rule:
        with st.expander(
            "Source — règle d'origine"
        ):
            st.write(
                origin_rule.get(
                    "source_excerpt",
                    "—",
                )
            )

            st.caption(
                (
                    f"{origin_rule.get('source_document', '')}"
                    f" — page "
                    f"{origin_rule.get('source_page', '—')}"
                )
            )

    if tariff_schedule:
        with st.expander(
            "Source — calendrier tarifaire"
        ):
            st.write(
                tariff_schedule.get(
                    "source_excerpt",
                    "—",
                )
            )

            st.caption(
                f"Page "
                f"{tariff_schedule.get('source_page', '—')}"
            )


def render_result(result):
    st.divider()

    render_classification(
        result
    )

    st.divider()

    render_standard_tariff(
        result
    )

    st.divider()

    render_preference(
        result
    )

    with st.expander(
        "Résultat technique complet"
    ):
        st.json(
            result,
            expanded=False,
        )


st.title(
    "Analyse réglementaire d'importation"
)

st.write(
    "Estimation des droits de douane et "
    "recherche des informations réglementaires "
    "à partir du corpus fourni."
)


with st.form(
    "import_analysis"
):
    produit = st.text_input(
        "Produit",
        placeholder=(
            "Ex. Écran LCD moniteur 27 pouces"
        ),
    )

    col1, col2 = st.columns(2)

    with col1:
        pays_exportateur = (
            st.text_input(
                "Pays exportateur",
                placeholder=(
                    "Ex. Corée du Sud"
                ),
            )
        )

    with col2:
        pays_importateur = (
            st.text_input(
                "Pays importateur",
                value="France",
            )
        )

    valeur_marchandise_eur = (
        st.number_input(
            "Valeur marchandise (€)",
            min_value=0.0,
            value=0.0,
            step=100.0,
        )
    )

    submitted = (
        st.form_submit_button(
            "Analyser l'importation",
            type="primary",
        )
    )


if submitted:
    if not produit.strip():
        st.error(
            "Veuillez renseigner "
            "une description produit."
        )

    elif not pays_exportateur.strip():
        st.error(
            "Veuillez renseigner "
            "le pays exportateur."
        )

    elif not pays_importateur.strip():
        st.error(
            "Veuillez renseigner "
            "le pays importateur."
        )

    elif valeur_marchandise_eur <= 0:
        st.error(
            "La valeur marchandise doit "
            "être supérieure à 0 €."
        )

    else:
        request = ImportRequest(
            produit=produit.strip(),
            pays_exportateur=(
                pays_exportateur.strip()
            ),
            pays_importateur=(
                pays_importateur.strip()
            ),
            valeur_marchandise_eur=(
                valeur_marchandise_eur
            ),
        )

        try:
            with st.spinner(
                "Analyse en cours..."
            ):
                result = evaluate_import(
                    request
                )

            render_result(
                result
            )

        except Exception as exc:
            st.error(
                "Une erreur est survenue "
                "pendant l'analyse."
            )

            with st.expander(
                "Détail technique"
            ):
                st.exception(
                    exc
                )