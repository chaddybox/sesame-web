from __future__ import annotations
from typing import Dict
import re

# Canonical header mapping:
# We normalize headers by lowercasing and removing all non-alphanumeric characters.
# Example: "Lys, % CP" -> "lyscp"
ALIASES: Dict[str, str] = {
    # identity
    "name": "name",
    "ingredient": "name",
    "feed": "name",
    "description": "name",
    "feedname": "name",

    # price
    "pricepert": "price_per_t",
    "priceperton": "price_per_t",
    "price": "price_per_t",
    "priceton": "price_per_t",
    "priceusdt": "price_per_t",

    # DM / proximate
    "dm": "DM",
    "drymatter": "DM",
    "ash": "Ash",
    "cp": "CP",
    "crudeprotein": "CP",
    "adf": "ADF",
    "ndf": "NDF",

    # protein partitions
    "rup": "RUP",
    "rumenundegradedprotein": "RUP",
    "bypasscp": "RUP",
    "bypasscp": "RUP",
    "rdp": "RDP",
    "rumendegradedprotein": "RDP",
    "degradablecp": "RDP",

    # energy
    "de": "DE",
    "debase": "DE",
    "demcalkg": "DE",
    "me": "ME",
    "nel": "NEL",

    # fiber digestibility
    "ndfd48": "NDFD48",
    "ndfd": "NDFD48",

    # carbs
    "starch": "Starch",
    "wsc": "WSC",
    "sugar": "WSC",

    # fats / fatty acids
    "totalfattyacids": "Total_Fatty_Acids",
    "totalfattyacidsdm": "Total_Fatty_Acids",
    "tfadm": "TFA_DM",
    "c181cistfa": "C18_1_cis",
    "c181transtfa": "C18_1_trans",

    # amino acids (% of CP)
    "argc p": "Arg_%CP",
    "argc p": "Arg_%CP",
    "argc p": "Arg_%CP",
    "argcp": "Arg_%CP",
    "hiscp": "His_%CP",
    "ilecp": "Ile_%CP",
    "leucp": "Leu_%CP",
    "lyscp": "Lys_%CP",
    "metcp": "Met_%CP",
    "phecp": "Phe_%CP",
    "thrcp": "Thr_%CP",
    "trpcp": "Trp_%CP",
    "valcp": "Val_%CP",
}

def canon_header(h: str) -> str:
    raw = (h or "").strip().lower()
    # remove everything except [a-z0-9]
    k = re.sub(r"[^a-z0-9]+", "", raw)
    return ALIASES.get(k, h.strip())
