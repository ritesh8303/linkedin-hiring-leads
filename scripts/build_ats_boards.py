"""Build / expand local ATS board config from DataForge seeds + global public boards."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config"


def main() -> None:
    boards = yaml.safe_load((CFG / "ats_boards.yaml").read_text(encoding="utf-8")) or {}
    for k in (
        "greenhouse",
        "ashby",
        "lever",
        "smartrecruiters",
        "workable",
        "recruitee",
        "pinpoint",
        "teamtailor",
        "comeet",
    ):
        boards.setdefault(k, [])

    dach = Path(r"D:\dataforge\config\sources\dach_ats.json")
    if dach.is_file():
        raw = json.loads(dach.read_text(encoding="utf-8"))
        for row in raw:
            url = (row.get("careers_url") or "").lower()
            m = re.search(r"boards\.greenhouse\.io/([^/?#]+)", url)
            if m:
                boards["greenhouse"].append(m.group(1))
                continue
            m = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)", url)
            if m:
                boards["ashby"].append(m.group(1))
                continue
            m = re.search(r"jobs\.lever\.co/([^/?#]+)", url)
            if m:
                boards["lever"].append(m.group(1))
                continue
            m = re.search(r"careers\.smartrecruiters\.com/([^/?#]+)", url)
            if m:
                boards["smartrecruiters"].append(m.group(1))
                continue
            m = re.search(r"apply\.workable\.com/([^/?#]+)", url)
            if m:
                boards["workable"].append(m.group(1))
                continue
            m = re.search(r"([a-z0-9-]+)\.recruitee\.com", url)
            if m:
                boards["recruitee"].append(m.group(1))
                continue
            m = re.search(r"([a-z0-9-]+)\.pinpointhq\.com", url)
            if m:
                boards["pinpoint"].append(m.group(1))

    extra_gh = (
        "airbnb asana figma notion discord dropbox hubspot intercom gitlab hashicorp nvidia "
        "snowflakecomputing duolingo robinhood coinbase plaid ramp brex rippling canva atlassian "
        "uber lyft doordash instacart squareup block affirm chime sofi gusto lattice mercury "
        "vercel linearapp retool dbtlabs fivetran airbyte confluent databricks stripe cloudflare "
        "mongodb elastic datadog openai anthropic deepmind huggingface spotify shopify twilio "
        "palantirtechnologies coursera okta box eventbrite snap reddit wayfair bookingcom "
        "expedia tripadvisor zendesk adobe intel amd qualcomm n26 hellofresh celonis contentful "
        "traderepublic getyourguide sumup raisin auto1group flix adyen wolt wise doctolib personio "
        "aboutyou check24 omio adjust deliveryhero crowdstrike zalando ticketmaster picsart "
        "messagebird tier revolut"
    ).split()
    boards["greenhouse"].extend(extra_gh)

    boards["ashby"].extend(
        (
            "deepl parloa langfuse mistral bolt juni pigment scaleway photoroom lovable "
            "helmholtzmunich perplexity elevenlabs runwayml cohere deepgram togetherai "
            "anyscale weightsandbiases langchain"
        ).split()
    )
    boards["lever"].extend(
        "twilio shopify palantir okta box dropbox eventbrite coursera duolingo reddit snap wayfair".split()
    )

    # Prefer known-live SmartRecruiters slugs
    prefer = {
        "boschgroup": "BoschGroup",
        "continental": "Continental",
        "deliveryhero": "DeliveryHero",
    }
    seen: set[str] = set()
    sr: list[str] = []
    for x in list(boards["smartrecruiters"]) + ["BoschGroup", "Continental", "DeliveryHero"]:
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        sr.append(prefer.get(k, x))
    boards["smartrecruiters"] = sr

    boards["workable"] = sorted(set(list(boards["workable"]) + ["huggingface"]))
    boards["recruitee"] = sorted(set(list(boards["recruitee"]) + ["bunq"]))
    boards["pinpoint"] = sorted(set(list(boards["pinpoint"]) + ["workwithus"]))
    boards["teamtailor"] = sorted(
        set(
            list(boards.get("teamtailor") or [])
            + [
                "einride.teamtailor.com",
                "epidemicsound.teamtailor.com",
                "bambuser.teamtailor.com",
                "karma.teamtailor.com",
                "mentimeter.teamtailor.com",
                "vinted.teamtailor.com",
                "truecaller.teamtailor.com",
            ]
        )
    )

    for k, v in list(boards.items()):
        if isinstance(v, list) and v and isinstance(v[0], str):
            boards[k] = sorted(set(v))

    workday = [
        {
            "company": "NVIDIA",
            "host": "https://nvidia.wd5.myworkdayjobs.com",
            "tenant": "nvidia",
            "site": "NVIDIAExternalCareerSite",
        },
        {
            "company": "Adobe",
            "host": "https://adobe.wd5.myworkdayjobs.com",
            "tenant": "adobe",
            "site": "external_experienced",
        },
        {
            "company": "Intel",
            "host": "https://intel.wd1.myworkdayjobs.com",
            "tenant": "intel",
            "site": "External",
        },
    ]

    (CFG / "ats_boards.yaml").write_text(
        yaml.dump(boards, sort_keys=True, allow_unicode=True), encoding="utf-8"
    )
    (CFG / "workday_targets.yaml").write_text(
        yaml.dump(workday, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    personio_src = Path(r"D:\dataforge\config\sources\personio_tenants.json")
    if personio_src.is_file():
        (CFG / "personio_tenants.json").write_text(
            personio_src.read_text(encoding="utf-8"), encoding="utf-8"
        )

    personio = json.loads((CFG / "personio_tenants.json").read_text(encoding="utf-8"))
    print("boards", {k: len(v) for k, v in boards.items()})
    print("personio", len(personio), "workday", len(workday))


if __name__ == "__main__":
    main()
