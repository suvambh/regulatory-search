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


# ============================================================
# Formatting
# ============================================================


STATUS_LABELS = {
    "SUPPORTED":
        "Déterminé",

    "UNCERTAIN_CLASSIFICATION":
        "Classification incertaine",

    "UNCERTAIN_APPLICABILITY":
        "Applicabilité incertaine",

    "NOT_APPLICABLE":
        "Non applicable",

    "STANDARD_RATE_NOT_DETERMINED":
        "Taux non déterminé",

    "NO_SUPPORTED_AGREEMENT":
        "Aucun accord pris en charge",

    "PREFERENCE_NOT_DETERMINED":
        "Préférence non déterminée",

    "CALCULATED_ON_ASSERTED_ORIGIN":
        "Préférence calculée",

    (
        "PREFERENTIAL_RATE_DETERMINED_"
        "WITH_CLASSIFICATION_UNCERTAINTY_"
        "ON_ASSERTED_ORIGIN"
    ):
        "Préférence déterminée avec "
        "classification douanière incertaine",
}


def format_money(value):
    if value is None:
        return None

    return f"{value:,.2f} €"


def format_rate(value):
    if value is None:
        return None

    return f"{value:g} %"


def format_status(status):
    if not status:
        return None

    return STATUS_LABELS.get(
        status,
        status,
    )


# ============================================================
# Source / citation helpers
# ============================================================


def get_source_text(
    source,
):
    return (
        source.get(
            "source_excerpt"
        )
        or source.get(
            "text"
        )
        or source.get(
            "rule_text"
        )
    )


def get_source_title(
    source,
):
    title = source.get(
        "title"
    )

    if title:
        return title

    article = source.get(
        "article"
    )

    if article:
        return (
            f"Article {article}"
        )

    rule = source.get(
        "provision_code"
    )

    if rule:
        return str(
            rule
        )

    return "Source réglementaire"


def get_source_reference(
    source,
):
    """
    Build a concise human-readable citation.

    Example:
    Règlement (UE) 2017/745 · Annexe VIII · page 143
    """

    parts = []

    document = (
        source.get(
            "source_document"
        )
        or source.get(
            "document_name"
        )
    )

    if document:
        parts.append(
            document
        )

    section = source.get(
        "source_section"
    )

    article = source.get(
        "article"
    )

    if section:
        parts.append(
            section
        )

    elif article:
        parts.append(
            f"Article {article}"
        )

    page = source.get(
        "source_page"
    )

    if page is not None:
        parts.append(
            f"page {page}"
        )

    return " · ".join(
        parts
    )


def render_source_group(
    title,
    sources,
):
    """
    Display several citations inside one compact
    expandable section.
    """

    sources = [
        source
        for source
        in sources
        if source
    ]

    if not sources:
        return

    with st.expander(
        title
    ):
        for index, source in enumerate(
            sources
        ):
            st.markdown(
                f"**{get_source_title(source)}**"
            )

            reference = (
                get_source_reference(
                    source
                )
            )

            if reference:
                st.caption(
                    f"📚 {reference}"
                )

            source_text = (
                get_source_text(
                    source
                )
            )

            if source_text:
                st.write(
                    source_text
                )

            if (
                index
                < len(sources) - 1
            ):
                st.divider()


# ============================================================
# Customs classification
# ============================================================


def render_classification(
    result,
):
    classification = result[
        "classification"
    ]

    st.subheader(
        "Classification douanière"
    )

    metrics = []

    nc_code = classification.get(
        "nc_code"
    )

    if nc_code:
        metrics.append(
            (
                "Code NC",
                nc_code,
            )
        )

    status = format_status(
        classification.get(
            "status"
        )
    )

    if status:
        metrics.append(
            (
                "Statut",
                status,
            )
        )

    if metrics:
        columns = st.columns(
            len(metrics)
        )

        for column, (
            label,
            value,
        ) in zip(
            columns,
            metrics,
        ):
            column.metric(
                label,
                value,
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
            "Informations supplémentaires "
            "requises : "
            + ", ".join(
                missing_information
            )
        )


# ============================================================
# Standard tariff
# ============================================================


def render_standard_tariff(
    result,
):
    tariff = result.get(
        "tariff"
    )

    if not tariff:
        return False

    st.subheader(
        "Droits de douane standard"
    )

    metrics = []

    hs_code = tariff.get(
        "hs_code"
    )

    if hs_code:
        metrics.append(
            (
                "Code HS",
                hs_code,
            )
        )

    standard_rate = format_rate(
        tariff.get(
            "standard_rate_pct"
        )
    )

    if standard_rate is not None:
        metrics.append(
            (
                "Taux standard",
                standard_rate,
            )
        )

    standard_duty = format_money(
        tariff.get(
            "standard_duty_eur"
        )
    )

    if standard_duty is not None:
        metrics.append(
            (
                "Droit estimé",
                standard_duty,
            )
        )

    if metrics:
        columns = st.columns(
            len(metrics)
        )

        for column, (
            label,
            value,
        ) in zip(
            columns,
            metrics,
        ):
            column.metric(
                label,
                value,
            )

    status = format_status(
        tariff.get(
            "status"
        )
    )

    if status:
        st.caption(
            f"Statut : {status}"
        )

    calculation_basis = tariff.get(
        "calculation_basis"
    )

    if calculation_basis:
        st.caption(
            f"Calcul : {calculation_basis}"
        )

    classification_note = tariff.get(
        "classification_note"
    )

    if classification_note:
        st.info(
            classification_note
        )

    return True


# ============================================================
# Preferential tariff / FTA
# ============================================================


def render_origin(
    preference,
):
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

    if not (
        origin_verification
        or origin_rule
    ):
        return

    st.markdown(
        "#### Origine préférentielle"
    )

    if origin_verification:

        status = (
            origin_verification.get(
                "status"
            )
        )

        reason = (
            origin_verification.get(
                "reason"
            )
        )

        if status == "NOT_VERIFIED":

            if reason:
                st.warning(
                    reason
                )

            else:
                st.warning(
                    "L'origine préférentielle "
                    "n'est pas vérifiée."
                )

        elif status:
            st.write(
                format_status(
                    status
                )
            )

    if origin_rule:
        rule_text = (
            origin_rule.get(
                "rule_text"
            )
        )

        hs_code = (
            origin_rule.get(
                "hs_code"
            )
        )

        with st.expander(
            "Règle d'origine applicable"
        ):

            if hs_code:
                st.caption(
                    f"HS4 : {hs_code}"
                )

            if rule_text:
                st.write(
                    rule_text
                )

            reference = (
                get_source_reference(
                    origin_rule
                )
            )

            if reference:
                st.caption(
                    f"📚 {reference}"
                )


def render_preference_sources(
    preference,
):
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

    if legal_basis:
        render_source_group(
            "Base juridique de l'accord",
            legal_basis,
        )

    if origin_rule:
        render_source_group(
            "Source — règle d'origine",
            [
                origin_rule
            ],
        )

    if tariff_schedule:
        render_source_group(
            "Source — calendrier tarifaire",
            [
                tariff_schedule
            ],
        )


def render_preference(
    result,
):
    preference = result.get(
        "preferential_tariff"
    )

    if not preference:
        return False

    agreement = (
        preference.get(
            "agreement"
        )
        or {}
    )

    # No agreement means no useful section
    # to display in the main UI.
    if not agreement:
        return False

    st.subheader(
        "Accord commercial"
    )

    agreement_name = (
        agreement.get(
            "agreement_name"
        )
    )

    if agreement_name:
        st.markdown(
            f"**{agreement_name}**"
        )

    status = format_status(
        preference.get(
            "status"
        )
    )

    if status:
        st.caption(
            f"Statut : {status}"
        )

    metrics = []

    preferential_rate = (
        format_rate(
            preference.get(
                "preferential_rate_pct"
            )
        )
    )

    if preferential_rate is not None:
        metrics.append(
            (
                "Taux préférentiel",
                preferential_rate,
            )
        )

    preferential_duty = (
        format_money(
            preference.get(
                "preferential_duty_eur"
            )
        )
    )

    if preferential_duty is not None:
        metrics.append(
            (
                "Droit préférentiel",
                preferential_duty,
            )
        )

    saving = format_money(
        preference.get(
            "saving_eur"
        )
    )

    if saving is not None:
        metrics.append(
            (
                "Économie potentielle",
                saving,
            )
        )

    if metrics:
        columns = st.columns(
            len(metrics)
        )

        for column, (
            label,
            value,
        ) in zip(
            columns,
            metrics,
        ):
            column.metric(
                label,
                value,
            )

    assumption = preference.get(
        "assumption"
    )

    if assumption:
        st.info(
            assumption
        )

    render_origin(
        preference
    )

    render_preference_sources(
        preference
    )

    return True


# ============================================================
# MDR / medical regulation
# ============================================================


def render_medical_regulation(
    result,
):
    medical = result.get(
        "medical_regulation"
    )

    if not medical:
        return False

    st.subheader(
        "Réglementation des dispositifs médicaux"
    )

    # --------------------------------------------------------
    # Regulatory framework
    # --------------------------------------------------------

    framework = (
        medical.get(
            "framework"
        )
        or {}
    )

    document_name = (
        framework.get(
            "document_name"
        )
    )

    if document_name:
        st.caption(
            f"Cadre réglementaire : "
            f"{document_name}"
        )

    # --------------------------------------------------------
    # Main result
    # --------------------------------------------------------

    metrics = []

    device_class = medical.get(
        "classification"
    )

    possible_classes = (
        medical.get(
            "possible_classes"
        )
        or []
    )

    if device_class:
        metrics.append(
            (
                "Classe MDR",
                device_class,
            )
        )

    elif possible_classes:
        metrics.append(
            (
                "Classes possibles",
                ", ".join(
                    possible_classes
                ),
            )
        )

    status = format_status(
        medical.get(
            "status"
        )
    )

    if status:
        metrics.append(
            (
                "Statut",
                status,
            )
        )

    if metrics:
        columns = st.columns(
            len(metrics)
        )

        for column, (
            label,
            value,
        ) in zip(
            columns,
            metrics,
        ):
            column.metric(
                label,
                value,
            )

    # --------------------------------------------------------
    # Classification explanation
    # --------------------------------------------------------

    reason = medical.get(
        "reason"
    )

    if reason:
        st.write(
            reason
        )

    missing_information = (
        medical.get(
            "missing_information"
        )
        or []
    )

    if missing_information:
        st.warning(
            "Informations nécessaires pour "
            "confirmer la classification : "
            + ", ".join(
                missing_information
            )
        )

    # --------------------------------------------------------
    # Classification rule
    # --------------------------------------------------------

    rules = (
        medical.get(
            "rules"
        )
        or []
    )

    if rules:
        st.markdown(
            "#### Règle de classification"
        )

        for rule in rules:
            rule_code = (
                rule.get(
                    "provision_code"
                )
            )

            if rule_code:
                st.write(
                    f"**Règle {rule_code}**"
                )

            reference = (
                get_source_reference(
                    rule
                )
            )

            if reference:
                st.caption(
                    f"📚 {reference}"
                )

    # --------------------------------------------------------
    # Main regulatory requirements
    # --------------------------------------------------------

    regulatory_basis = (
        medical.get(
            "regulatory_basis"
        )
        or []
    )

    provision_ids = {
        provision.get(
            "provision_id"
        )
        for provision
        in regulatory_basis
    }

    requirements = []

    if (
        "MDR_ARTICLE_20"
        in provision_ids
    ):
        requirements.append(
            "Marquage CE"
        )

    if (
        "MDR_ARTICLE_19"
        in provision_ids
    ):
        requirements.append(
            "Déclaration UE de conformité"
        )

    if (
        "MDR_ANNEX_II_PAGE_108"
        in provision_ids
    ):
        requirements.append(
            "Documentation technique"
        )

    if (
        "MDR_ARTICLE_52"
        in provision_ids
    ):
        requirements.append(
            "Évaluation de conformité "
            "selon la classe du dispositif"
        )

    if (
        "MDR_ARTICLE_53"
        in provision_ids
    ):
        requirements.append(
            "Intervention d'un organisme "
            "notifié lorsque requise"
        )

    if requirements:
        st.markdown(
            "#### Principales exigences"
        )

        for requirement in requirements:
            st.markdown(
                f"- ✓ {requirement}"
            )

    # --------------------------------------------------------
    # Sources
    #
    # Only show the most useful legal sources.
    # Definitions and other internal reasoning evidence
    # remain available in the technical JSON.
    # --------------------------------------------------------

    important_source_ids = {
        "MDR_ARTICLE_19",
        "MDR_ARTICLE_20",
        "MDR_ARTICLE_52",
        "MDR_ARTICLE_53",
        "MDR_ANNEX_II_PAGE_108",
    }

    important_sources = [
        provision
        for provision
        in regulatory_basis
        if provision.get(
            "provision_id"
        )
        in important_source_ids
    ]

    all_sources = (
        rules
        + important_sources
    )

    if all_sources:
        st.markdown(
            "#### Sources réglementaires"
        )

        render_source_group(
            "Voir les sources",
            all_sources,
        )

    return True


# ============================================================
# Complete result
# ============================================================


def render_result(
    result,
):
    st.divider()

    render_classification(
        result
    )

    if result.get(
        "tariff"
    ):
        st.divider()

        render_standard_tariff(
            result
        )

    preference = result.get(
        "preferential_tariff"
    )

    if (
        preference
        and preference.get(
            "agreement"
        )
    ):
        st.divider()

        render_preference(
            result
        )

    if result.get(
        "medical_regulation"
    ):
        st.divider()

        render_medical_regulation(
            result
        )

    st.divider()

    with st.expander(
        "Résultat technique complet"
    ):
        st.json(
            result,
            expanded=False,
        )


# ============================================================
# Application
# ============================================================


st.title(
    "Analyse réglementaire d'importation"
)

st.write(
    "Estimation des droits de douane et "
    "analyse des exigences réglementaires "
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

    col1, col2 = st.columns(
        2
    )

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
            produit=(
                produit.strip()
            ),

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
                result = (
                    evaluate_import(
                        request
                    )
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