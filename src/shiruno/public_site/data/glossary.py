"""Static dojo-terminology glossary for the Traditional Karate-Do page
(feature 005-public-club-website)."""

from shiruno.public_site.models import GlossaryTerm

GLOSSARY_TERMS: tuple[GlossaryTerm, ...] = (
    GlossaryTerm(
        term="Mokuso",
        category="Komenda/etykieta",
        explanation=(
            "Krótka chwila medytacji w ciszy, zwykle z zamkniętymi oczami, "
            "wykonywana na początku i na końcu treningu, aby wyciszyć umysł."
        ),
    ),
    GlossaryTerm(
        term="Seiza",
        category="Komenda/etykieta",
        explanation="Formalna pozycja siedząca na piętach, przyjmowana podczas mokuso i powitań.",
    ),
    GlossaryTerm(
        term="Rei",
        category="Komenda/etykieta",
        explanation="Ukłon — wyraz szacunku wobec dojo, instruktora i partnera treningowego.",
    ),
    GlossaryTerm(
        term="Kiai",
        category="Komenda/etykieta",
        explanation=(
            "Krótki, mocny okrzyk towarzyszący wykonaniu techniki — wyraz "
            "koncentracji i uwolnienia energii w danym momencie."
        ),
    ),
    GlossaryTerm(
        term="Kihon",
        category="Technika",
        explanation=(
            "Podstawowe techniki karate — uderzenia, bloki i kopnięcia ćwiczone w izolacji."
        ),
    ),
    GlossaryTerm(
        term="Kata",
        category="Technika",
        explanation=(
            "Ułożona sekwencja technik wykonywana samodzielnie, symulująca "
            "walkę z wieloma przeciwnikami."
        ),
    ),
    GlossaryTerm(
        term="Kumite",
        category="Technika",
        explanation="Walka — kontrolowana wymiana technik z partnerem, od formy umownej po wolną.",
    ),
    GlossaryTerm(
        term="Gyaku Tsuki",
        category="Technika",
        explanation="Cios prosty wykonywany ręką przeciwną do wysuniętej nogi („cios odwrotny”).",
    ),
    GlossaryTerm(
        term="Oi Tsuki",
        category="Technika",
        explanation="Cios prosty wykonywany ręką tej samej strony, co wysunięta noga.",
    ),
)
