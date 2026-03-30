from __future__ import annotations

from typing import Dict, List

PRESETS: List[Dict[str, object]] = [
    {
        "label": "1) Basic Energy + Protein (DE, CP)",
        "summary_label": "Basic Energy + Protein (DE, CP)",
        "columns": ["DE", "CP"],
    },
    {
        "label": "2) Energy + Digestible RUP Protein (DE, dRUP_prot)",
        "summary_label": "Energy + Digestible RUP Protein (DE, dRUP_prot)",
        "columns": ["DE", "dRUP_prot"],
    },
    {
        "label": "3) Energy + Digestible RUP Protein + Digestible NDF (DE, dRUP_prot, NDFd)",
        "summary_label": "Energy + Digestible RUP Protein + Digestible NDF (DE, dRUP_prot, NDFd)",
        "columns": ["DE", "dRUP_prot", "NDFd"],
    },
    {
        "label": "4) Energy + Digestible RUP Protein + Digestible NDF + Fat (DE, dRUP_prot, NDFd, TFA)",
        "summary_label": "Energy + Digestible RUP Protein + Digestible NDF + Fat (DE, dRUP_prot, NDFd, TFA)",
        "columns": ["DE", "dRUP_prot", "NDFd", "Total_Fatty_Acids"],
    },
    {
        "label": "5) NASEM Eq. 6-6 Milk Protein Yield (locked)",
        "summary_label": "NASEM Eq. 6-6 Milk Protein Yield",
        "columns": ["NASEM_MP_6_6_perkgDM"],
        "locked": True,
        "locked_message": (
            "This preset is locked because NASEM Eq. 6-6 Milk Protein Yield is a derived "
            "composite variable. Additional nutrient selection is disabled for this preset."
        ),
    },
    {
        "label": "6) Branched-Chain AA (dRUP)",
        "summary_label": "Branched-Chain AA (dRUP)",
        "columns": ["dLeu_RUP", "dIle_RUP", "dVal_RUP"],
    },
    {
        "label": "7) Lys, Met, His (dRUP)",
        "summary_label": "Lys, Met, His (dRUP)",
        "columns": ["dLys_RUP", "dMet_RUP", "dHis_RUP"],
    },
    {
        "label": "8) Fat (TFA, % DM)",
        "summary_label": "Fat (TFA, % DM)",
        "columns": ["Total_Fatty_Acids"],
    },
]

NUTRIENT_GROUPS: List[Dict[str, object]] = [
    {
        "label": "Energy",
        "options": [
            {"column": "DE", "label": "DE (Digestible Energy, Mcal/kg DM)"},
        ],
    },
    {
        "label": "Protein",
        "options": [
            {"column": "CP", "label": "Crude Protein (CP, % DM)"},
            {"column": "dRUP_prot", "label": "Digestible RUP protein (% DM)"},
            {
                "column": "NASEM_MP_6_6_perkgDM",
                "label": "NASEM Eq. 6-6 Milk Protein Yield (derived composite)",
            },
        ],
    },
    {
        "label": "Amino Acids",
        "options": [
            {"column": "dArg_RUP", "label": "Arginine (dRUP, % DM)"},
            {"column": "dHis_RUP", "label": "Histidine (dRUP, % DM)"},
            {"column": "dIle_RUP", "label": "Isoleucine (dRUP, % DM)"},
            {"column": "dLeu_RUP", "label": "Leucine (dRUP, % DM)"},
            {"column": "dLys_RUP", "label": "Lysine (dRUP, % DM)"},
            {"column": "dMet_RUP", "label": "Methionine (dRUP, % DM)"},
            {"column": "dPhe_RUP", "label": "Phenylalanine (dRUP, % DM)"},
            {"column": "dThr_RUP", "label": "Threonine (dRUP, % DM)"},
            {"column": "dTrp_RUP", "label": "Tryptophan (dRUP, % DM)"},
            {"column": "dVal_RUP", "label": "Valine (dRUP, % DM)"},
        ],
    },
    {
        "label": "Carbohydrates",
        "options": [
            {"column": "ADF", "label": "ADF (% DM)"},
            {"column": "NDF", "label": "NDF (% DM)"},
            {"column": "NDFD48", "label": "NDFD48 (% of NDF)"},
            {"column": "NDFd", "label": "Digestible NDF (% DM)"},
            {"column": "Starch", "label": "Starch (% DM)"},
            {"column": "WSC", "label": "WSC (% DM)"},
        ],
    },
    {
        "label": "Fat",
        "options": [
            {"column": "Total_Fatty_Acids", "label": "TFAs (% DM)"},
            {"column": "C12_0_DM", "label": "Lauric acid (C12:0, % DM)"},
            {"column": "C14_0_DM", "label": "Myristic acid (C14:0, % DM)"},
            {"column": "C16_0_DM", "label": "Palmitic acid (C16:0, % DM)"},
            {"column": "C16_1_DM", "label": "Palmitoleic acid (C16:1, % DM)"},
            {"column": "C18_0_DM", "label": "Stearic acid (C18:0, % DM)"},
            {"column": "C18_1_trans_DM", "label": "Trans C18:1 fatty acids (C18:1 trans, % DM)"},
            {"column": "C18_1_cis_DM", "label": "Oleic acid (C18:1 cis, % DM)"},
            {"column": "C18_2_DM", "label": "Linoleic acid (C18:2, % DM)"},
            {"column": "C18_3_DM", "label": "Linolenic acid (C18:3, % DM)"},
            {"column": "Other_Fatty_Acids_DM", "label": "Others (% DM)"},
        ],
    },
    {
        "label": "Minerals",
        "options": [
            {"column": "Ca", "label": "Calcium (Ca, % DM)"},
            {"column": "P", "label": "Phosphorus (P, % DM)"},
            {"column": "Mg", "label": "Magnesium (Mg, % DM)"},
            {"column": "K", "label": "Potassium (K, % DM)"},
            {"column": "Na", "label": "Sodium (Na, % DM)"},
            {"column": "Cl", "label": "Chloride (Cl, % DM)"},
            {"column": "S", "label": "Sulfur (S, % DM)"},
        ],
    },
]

NUTRIENT_OPTIONS_BY_COLUMN: Dict[str, Dict[str, str]] = {
    option["column"]: option
    for group in NUTRIENT_GROUPS
    for option in group["options"]
}


def preset_columns(preset_index: int) -> List[str]:
    preset = PRESETS[preset_index]
    return list(preset["columns"])