"""Static news posts for the public website (fictional demo content —
feature 005-public-club-website)."""

from datetime import date

from shiruno.public_site.models import NewsPost

NEWS_POSTS: tuple[NewsPost, ...] = (
    NewsPost(
        slug="nowy-sezon-treningowy-2026",
        title="Startuje nowy sezon treningowy 2026/2027",
        date=date(2026, 8, 25),
        category="Sezon",
        summary="Zapisy na nowy sezon treningowy są już otwarte we wszystkich sekcjach ALBERTOS.",
        body=(
            "Z przyjemnością ogłaszamy start nowego sezonu treningowego "
            "2026/2027 we wszystkich sekcjach ALBERTOS.",
            "Zapisy prowadzimy na zajęcia dla dzieci, młodzieży i dorosłych — "
            "niezależnie od poziomu zaawansowania. Pierwszy tydzień treningów "
            "jest doskonałą okazją, aby spróbować swoich sił bez zobowiązań.",
            "Szczegółowy grafik zajęć znajdziesz w zakładce Grafik.",
        ),
        image_alt="Grupa trenujących na macie w sali gimnastycznej",
    ),
    NewsPost(
        slug="obóz-letni-2026",
        title="Zapisy na letni obóz karate 2026",
        date=date(2026, 5, 10),
        category="Obóz",
        summary="Tygodniowy obóz treningowy dla dzieci i młodzieży — zapisy trwają.",
        body=(
            "Tegoroczny letni obóz karate odbędzie się w otoczeniu lasów i "
            "jezior — połączenie intensywnych treningów z aktywnym "
            "wypoczynkiem.",
            "W programie codzienne treningi kihon, kata i kumite, zajęcia "
            "integracyjne oraz wspólne ognisko na zakończenie obozu.",
        ),
        image_alt="Grupa dzieci trenujących karate na zewnątrz podczas obozu",
    ),
    NewsPost(
        slug="egzamin-na-stopnie-kyu-czerwiec-2026",
        title="Egzamin na stopnie kyu — czerwiec 2026",
        date=date(2026, 6, 13),
        category="Egzaminy",
        summary="Kolejny egzamin na stopnie kyu odbędzie się w czerwcu — zapisy u instruktorów.",
        body=(
            "Zapraszamy wszystkich chętnych do przystąpienia do egzaminu na "
            "kolejne stopnie kyu. Warunkiem udziału jest zgoda instruktora "
            "prowadzącego oraz regularna obecność na treningach.",
            "Szczegóły dotyczące wymagań na poszczególne stopnie omawiamy "
            "indywidualnie z każdym uczestnikiem przed egzaminem.",
        ),
        image_alt=None,
    ),
    NewsPost(
        slug="puchar-grodzina-2026",
        title="ALBERTOS na Pucharze Grodzina",
        date=date(2026, 4, 2),
        category="Wydarzenia",
        summary="Nasi zawodnicy wystartowali w lokalnym turnieju, przywożąc komplet medali.",
        body=(
            "Reprezentacja ALBERTOS wzięła udział w Pucharze Grodzina, "
            "zdobywając łącznie osiem medali w konkurencjach kata i kumite.",
            "Gratulujemy wszystkim zawodnikom postawy i zaangażowania — to "
            "efekt regularnej, sumiennej pracy na treningach.",
        ),
        image_alt="Zawodnicy ALBERTOS z medalami po turnieju",
    ),
    NewsPost(
        slug="nowa-grupa-dla-najmlodszych",
        title="Nowa grupa dla najmłodszych w Grodzinie",
        date=date(2026, 3, 1),
        category="Nowa grupa",
        summary="Uruchamiamy nową grupę początkującą dla dzieci w sekcji Grodzin — SP-5.",
        body=(
            "Z uwagi na rosnące zainteresowanie zajęciami dla najmłodszych "
            "uruchamiamy nową grupę początkującą w sekcji Grodzin — SP-5.",
            "Zajęcia prowadzone są w przyjaznej, bezpiecznej atmosferze i "
            "kładą nacisk na rozwój koordynacji ruchowej oraz podstawowej "
            "dyscypliny.",
        ),
        image_alt=None,
    ),
)
