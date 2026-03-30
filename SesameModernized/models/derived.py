from __future__ import annotations
from typing import Dict, Any

# Essential AA list used for sums
EAA_KEYS = ["Arg", "His", "Ile", "Leu", "Lys", "Met", "Phe", "Thr", "Trp", "Val"]
FATTY_ACID_KEYS = [
    "C12_0",
    "C14_0",
    "C16_0",
    "C16_1",
    "C18_0",
    "C18_1_trans",
    "C18_1_cis",
    "C18_2",
    "C18_3",
    "Other_Fatty_Acids",
]


def _pct(x):
    """Return x/100 if x looks like a percent (already numeric)."""
    if x is None:
        return None
    try:
        return float(x) / 100.0
    except Exception:
        return None


def add_amino_acid_representations(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Generate AA representations needed for presets.

    Assumptions:
      - CP is % of DM
      - AA_%CP columns are % of CP (e.g., Lys_%CP = 6.2 means 6.2% of CP is Lys)
      - RUP is % of CP
      - dRUP is % digestibility of RUP protein in the intestine

    Outputs (all % of DM unless noted):
      - <AA>_DM : AA as % of DM (e.g., Lys_DM)
      - d<AA>_RUP : digestible AA supply from RUP as % of DM (e.g., dLys_RUP)
      - dEAA_RUP_sum : sum of digestible supply in RUP of all EAA (%DM)
      - dBCAA_RUP_sum : sum of digestible supply in RUP of Leu, Ile, Val (%DM)
      - dMetLysHis_RUP_sum : sum of digestible Met+Lys+His in RUP (%DM)
    """
    cp = rec.get("CP")          # %DM
    rup = rec.get("RUP")        # % of CP
    drup = rec.get("dRUP")      # % digestibility of RUP

    if cp is None:
        return rec

    rup_f = _pct(rup) if rup is not None else None
    drup_f = _pct(drup) if drup is not None else None

    d_eaa_sum = 0.0
    d_bcaa_sum = 0.0
    d_met_lys_his = 0.0

    for aa in EAA_KEYS:
        aa_pctcp = rec.get(f"{aa}_%CP")
        if aa_pctcp is None:
            continue
        aa_f = _pct(aa_pctcp)
        if aa_f is None:
            continue

        # AA as % of DM
        rec[f"{aa}_DM"] = cp * aa_f

        # Digestible AA in RUP as % of DM
        if rup_f is not None and drup_f is not None:
            d_aa = cp * rup_f * drup_f * aa_f
            rec[f"d{aa}_RUP"] = d_aa
            d_eaa_sum += d_aa

            if aa in ("Leu", "Ile", "Val"):
                d_bcaa_sum += d_aa

            if aa in ("Met", "Lys", "His"):
                d_met_lys_his += d_aa

    if d_eaa_sum > 0:
        rec["dEAA_RUP_sum"] = d_eaa_sum
        rec["dBCAA_RUP_sum"] = d_bcaa_sum
        rec["dMetLysHis_RUP_sum"] = d_met_lys_his

    return rec


def add_feed_level_proxies(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Compute additional feed-level proxy variables used in presets.

    Outputs:
      - RDP_prot : rumen degradable protein as %DM = CP * (1 - RUP/100)
      - dRUP_prot : digestible RUP protein as %DM = CP * (RUP/100) * (dRUP/100)
      - MP : simple workaround MP proxy (%DM). For now, MP := dRUP_prot.
      - NDFd : digestible NDF proxy (%DM) = NDF * (NDFD48/100)
      - Oleic_DM : oleic acid as %DM = TFA_DM * (C18_1_cis/100)
      - dRUP_plus_Oleic : dRUP_prot + Oleic_DM
    """
    cp = rec.get("CP")
    rup = rec.get("RUP")
    drup = rec.get("dRUP")

    if cp is not None and rup is not None:
        rup_f = _pct(rup)
        if rup_f is not None:
            # RDP as degradable protein supply, %DM
            rec["RDP_prot"] = cp * (1.0 - rup_f)

            # Digestible RUP protein supply, %DM
            if drup is not None:
                drup_f = _pct(drup)
                if drup_f is not None:
                    dRUP_prot = cp * rup_f * drup_f
                    rec["dRUP_prot"] = dRUP_prot

                    # Simple MP proxy if not already present
                    if rec.get("MP") is None:
                        rec["MP"] = dRUP_prot

    ndf = rec.get("NDF")
    ndfd48 = rec.get("NDFD48")
    if ndf is not None and ndfd48 is not None:
        ndfd_f = _pct(ndfd48)
        if ndfd_f is not None:
            rec["NDFd"] = ndf * ndfd_f

    if rec.get("Total_Fatty_Acids") is None and rec.get("TFA_DM") is not None:
        rec["Total_Fatty_Acids"] = rec["TFA_DM"]
    if rec.get("TFA_DM") is None and rec.get("Total_Fatty_Acids") is not None:
        rec["TFA_DM"] = rec["Total_Fatty_Acids"]

    tfa_dm = rec.get("TFA_DM")
    if tfa_dm is not None:
        for key in FATTY_ACID_KEYS:
            fa_pct = rec.get(key)
            fa_fraction = _pct(fa_pct)
            if fa_fraction is not None:
                rec[f"{key}_DM"] = tfa_dm * fa_fraction

    if rec.get("Oleic_DM") is None and rec.get("C18_1_cis_DM") is not None:
        rec["Oleic_DM"] = rec["C18_1_cis_DM"]

    if rec.get("dRUP_prot") is not None and rec.get("Oleic_DM") is not None:
        rec["dRUP_plus_Oleic"] = rec["dRUP_prot"] + rec["Oleic_DM"]

    # NASEM 2021 Eq. 6-6 milk protein contribution proxy (per kg DM basis)
    # Uses digestible AA in RUP, DE, and digestible NDF; BW fixed at 700 kg.
    # Units mapping to Eq. 6-6 inputs:
    #   - dAA_RUP variables are in %DM, converted to g/kg DM by multiplying by 10
    #   - DE is used as provided by feed library (commonly Mcal/kg DM)
    #   - dNDF is proxied as NDFd = NDF * NDFD48/100 (%DM)
    #   - BW constant is 700 kg
    de = rec.get("DE")
    ndfd = rec.get("NDFd")
    drup_prot = rec.get("dRUP_prot")
    his = rec.get("dHis_RUP")
    ile = rec.get("dIle_RUP")
    leu = rec.get("dLeu_RUP")
    lys = rec.get("dLys_RUP")
    met = rec.get("dMet_RUP")

    if all(v is not None for v in (de, ndfd, drup_prot, his, ile, leu, lys, met)):
        # Convert digestible AA and digestible RUP protein from %DM to g/kg DM
        his_gkg = his * 10.0
        ile_gkg = ile * 10.0
        leu_gkg = leu * 10.0
        lys_gkg = lys * 10.0
        met_gkg = met * 10.0
        drup_prot_gkg = drup_prot * 10.0

        # OthAA = NEAA + Arg + Phe + Thr + Trp + Val; approximated here as
        # digestible RUP protein minus the 5 EAA explicitly included in Eq. 6-6.
        othaa_gkg = drup_prot_gkg - (his_gkg + ile_gkg + leu_gkg + lys_gkg + met_gkg)

        rec["NASEM_MP_6_6_perkgDM"] = (
            -97.0
            + 1.68 * his_gkg
            + 0.885 * ile_gkg
            + 0.466 * leu_gkg
            + 1.15 * lys_gkg
            + 1.84 * met_gkg
            + 0.077 * othaa_gkg
            - 0.00215 * (
                his_gkg ** 2 + ile_gkg ** 2 + leu_gkg ** 2 + lys_gkg ** 2 + met_gkg ** 2
            )
            + 10.8 * de
            - 4.60 * (ndfd - 17.06)
            - 0.420 * (700.0 - 612.0)
        )

    return rec


def add_derived(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Bundle any safe derivations here."""
    rec = add_amino_acid_representations(rec)
    rec = add_feed_level_proxies(rec)
    return rec
