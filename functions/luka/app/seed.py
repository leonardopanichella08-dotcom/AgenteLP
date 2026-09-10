from __future__ import annotations

from sqlalchemy import select

from .db import SessionLocal
from .deps import get_or_create_user
from .models import BrandProfile, LinkedInConnection, SearchConfig


def seed_demo() -> None:
    """Crea un utente + due connessioni demo se il DB e' vuoto. Idempotente."""
    db = SessionLocal()
    try:
        user = get_or_create_user(db)
        existing = db.scalar(
            select(LinkedInConnection).where(LinkedInConnection.user_id == user.id)
        )
        if existing is not None:
            return

        personal = LinkedInConnection(
            user_id=user.id,
            account_type="personal",
            display_name="Marco Rossi",
            headline="Fondatore @ Nimbus AI | Sales intelligence per team B2B",
            industry="Software B2B",
            vanity_url="https://www.linkedin.com/in/marco-rossi-demo",
            raw_about=(
                "Aiuto i team di vendita B2B a qualificare gli account giusti prima "
                "dell'outreach. Prima ho guidato le vendite in due scale-up SaaS. "
                "Nimbus AI analizza i segnali di intent e riduce il tempo speso su "
                "account che non chiuderanno mai."
            ),
            scopes=[],
        )
        company = LinkedInConnection(
            user_id=user.id,
            account_type="company",
            display_name="Nimbus AI",
            headline="Sales intelligence che qualifica gli account B2B prima dell'outreach",
            industry="Software B2B",
            vanity_url="https://www.linkedin.com/company/nimbus-ai-demo",
            raw_about=(
                "Nimbus AI e' una piattaforma di sales intelligence. Analizziamo "
                "segnali comportamentali e firmografici per dire ai team GTM quali "
                "account meritano tempo umano. Clienti: scale-up SaaS 50-500 dipendenti "
                "in Europa."
            ),
            scopes=[],
        )
        db.add_all([personal, company])
        db.commit()
        db.refresh(personal)
        db.refresh(company)

        db.add_all(
            [
                BrandProfile(
                    connection_id=personal.id,
                    mission="Marco aiuta i team sales B2B a concentrare il tempo sugli account con reale probabilita' di chiusura.",
                    value_proposition="Meno volume, piu' segnale: qualificazione degli account prima dell'outreach.",
                    icp="VP Sales e RevOps in scale-up SaaS europee (50-500 dipendenti) con pipeline multi-prodotto.",
                    market_context="Mercato sales-tech saturo di tool di automazione che aumentano il volume ma non la qualita'; poco posizionamento chiaro.",
                    tone_of_voice="autorevole, diretto, concreto, senza buzzword",
                    generated_by_model="seed",
                ),
                BrandProfile(
                    connection_id=company.id,
                    mission="Nimbus AI dice ai team GTM quali account B2B meritano tempo umano.",
                    value_proposition="Qualificazione predittiva degli account basata su segnali di intent e dati firmografici.",
                    icp="Team GTM di scale-up SaaS 50-500 dipendenti in Europa.",
                    market_context="Sales intelligence B2B: molta offerta, differenziazione debole, buyer scettici verso l'AI generica.",
                    tone_of_voice="competente, sobrio, orientato ai risultati",
                    generated_by_model="seed",
                ),
                SearchConfig(
                    connection_id=personal.id,
                    name="AI B2B - Italia",
                    niche="AI B2B / Sales Intelligence",
                    keywords_primary=["sales", "automation", "icp", "outbound"],
                    keywords_secondary=["revops", "pipeline", "forecast"],
                    geo="italy",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()
