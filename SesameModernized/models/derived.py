from __future__ import annotations
from typing import Dict, Any

# Essential AA list used for sums
EAA_KEYS = ["Arg", "His", "Ile", "Leu", "Lys", "Met", "Phe", "Thr", "Trp", "Val"]


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

    tfa_dm = rec.get("TFA_DM")
    c181cis = rec.get("C18_1_cis")
    if tfa_dm is not None and c181cis is not None:
        c181_f = _pct(c181cis)
        if c181_f is not None:
            rec["Oleic_DM"] = tfa_dm * c181_f

    if rec.get("dRUP_prot") is not None and rec.get("Oleic_DM") is not None:
        rec["dRUP_plus_Oleic"] = rec["dRUP_prot"] + rec["Oleic_DM"]

    return rec


def add_derived(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Bundle any safe derivations here."""
    rec = add_amino_acid_representations(rec)
    rec = add_feed_level_proxies(rec)
    return rec