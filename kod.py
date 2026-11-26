import csv
import matplotlib.pyplot as plt
import requests
import json
from google import genai
from abc import ABC, abstractmethod
from datetime import datetime

#vytvoření struktury obecné transakce
class SurovaTransakce:
    def __init__(
        self,
        id_transakce: str,
        muj_ucet: str,
        datum: str,
        castka: float,
        mena: str,
        protiucet: str,
        popis: str,
    ):
        self.id_transakce = id_transakce
        self.muj_ucet = muj_ucet
        self.datum = datetime.strptime(datum, "%d.%m.%Y").date()
        self.castka = castka
        self.mena = mena
        self.protiucet = protiucet
        self.popis = popis

    def __str__(self) -> str:
        return (
            f"[{self.datum.strftime('%d.%m.%Y')}] Účet: {self.muj_ucet} | "
            f"Částka: {self.castka:>9.2f} {self.mena} | "
            f"Protiúčet: {self.protiucet:<14} | {self.popis}"
        )


#načtení dat z csv soubroů
class CsvZdrojDat(ABC):
    @abstractmethod
    def nacti_transakce(self) -> list[SurovaTransakce]:
        pass
    def __init__(self, cesta_k_souboru: str):
        self.cesta_k_souboru = cesta_k_souboru

    def _preved_castku(self, text_castky: str) -> float:
        ocisteno = text_castky.replace(" ", "").replace(",", ".")
        return float(ocisteno)

    def _spoj_ucet(self, cislo: str, kod_banky: str) -> str:
        cislo = cislo.strip()
        kod_banky = kod_banky.strip()
        if cislo and kod_banky:
            return f"{cislo}/{kod_banky}"
        return cislo if cislo else "Neznámý účet"

#přizpůsobení na ČSOB
class CsobCsvZdroj(CsvZdrojDat):
    def nacti_transakce(self) -> list[SurovaTransakce]:
        transakce_seznam = []

        with open(self.cesta_k_souboru, mode="r", encoding="utf-8-sig") as soubor:
            ctecky = csv.DictReader(soubor, delimiter=";")

            for radek in ctecky:
                protiucet = self._spoj_ucet(
                    radek["číslo protiúčtu"], radek["kód banky protiúčtu"]
                )
                popis = radek["zpráva"].strip() or radek["jméno protistrany"].strip()

                t = SurovaTransakce(
                    id_transakce=radek["ID transakce"].strip(),
                    muj_ucet=radek["číslo účtu"].strip(),
                    datum=radek["datum zaúčtování"].strip(),
                    castka=self._preved_castku(radek["částka"]),
                    mena=radek["měna"].strip(),
                    protiucet=protiucet,
                    popis=popis,
                )
                transakce_seznam.append(t)

        return transakce_seznam

#přizpůsobení na Monetu
class MonetaCsvZdroj(CsvZdrojDat):
    def nacti_transakce(self) -> list[SurovaTransakce]:
        transakce_seznam = []

        with open(self.cesta_k_souboru, mode="r", encoding="utf-8-sig") as soubor:
            ctecky = csv.DictReader(soubor, delimiter=";")

            for radek in ctecky:
                protiucet = self._spoj_ucet(
                    radek["Číslo protiúčtu"], radek["Banka protiúčtu"]
                )
                popis = (
                    radek["Zpráva pro příjemce"].strip()
                    or radek["Popis platby"].strip()
                    or radek["Název účtu příjemce"].strip()
                )

                t = SurovaTransakce(
                    id_transakce=radek["Bankovní reference"].strip(),
                    muj_ucet=radek["Číslo účtu"].strip(),
                    datum=radek["Odesláno"].strip(),
                    castka=self._preved_castku(radek["Částka"]),
                    mena=radek["Měna"].strip(),
                    protiucet=protiucet,
                    popis=popis,
                )
                transakce_seznam.append(t)

        return transakce_seznam

class Transakce:
    def __init__(self, surova: SurovaTransakce):
        self.id_transakce = surova.id_transakce
        self.muj_ucet = surova.muj_ucet
        self.datum = surova.datum
        self.castka = surova.castka
        self.mena = surova.mena
        self.protiucet = surova.protiucet
        self.popis = surova.popis

    def typ_operace(self) -> str:
        return "NEURČENO"

    def __str__(self) -> str:
        return (
            f"[{self.typ_operace():^6}] [{self.datum.strftime('%d.%m.%Y')}] "
            f"Účet: {self.muj_ucet} | Částka: {self.castka:>9.2f} {self.mena} | "
            f"Protiúčet: {self.protiucet:<14} | {self.popis}"
        )


class Prevod(Transakce):
    def typ_operace(self) -> str:
        return "PŘEVOD"


class Prijem(Transakce):
    def typ_operace(self) -> str:
        return "PŘÍJEM"


class Vydaj(Transakce):
    def __init__(self, surova: SurovaTransakce):
        super().__init__(surova)        #kategorizace výdajů
        self.kategorie = "Nezařazeno"

    def typ_operace(self) -> str:
        return "VÝDAJ"

    def __str__(self) -> str:
        return f"{super().__str__()} | Kategorie: {self.kategorie}"

class TridicTransakci:
    def __init__(self, surove_transakce: list[SurovaTransakce]):
        self.surove_transakce = surove_transakce
        self.moje_ucty = {t.muj_ucet for t in surove_transakce}

    def roztrid(self) -> list[Transakce]:
        vysledek = []
        for t in self.surove_transakce:
            if t.protiucet in self.moje_ucty:
                vysledek.append(Prevod(t))
            elif t.castka > 0:
                vysledek.append(Prijem(t))
            else:
                vysledek.append(Vydaj(t))
        return vysledek

class kategorizace(ABC):
    @abstractmethod
    def urci_kategorii(self, vydaj: Vydaj) -> str:
        pass

class KlicovaSlovaKategorizace(kategorizace):
    def __init__(self):
        self.pravidla = {
            "Potraviny": ["albert", "lidl", "globus", "tesco", "penny", "billa", "potraviny", "supermarket"],
            "Restaurace": ["pizza", "restaurace", "hospoda", "hospudka", "obcerstveni", "občerstvení",
                "mcdonald's","mcdonalds", "kfc", "popeyes", "burger king", "bar", "bistro", "kavárna", 
                "qerko", "restaurant",],
             "Bydlení": ["nájem", "najem", "elektřina", "voda", "suz.cvut.cz"],
             "Oblečení a Obuv": ["oblečení", "newyorker", "sinsay", "h&m", "deichmann", "ccc", "takko"],
             "Elektronika": ["alza", "elektroniky","datart","google","canva"],
             "Další nákupy": [ "temu", "knihobot", "luxor", "knihkupectvi","knihkupectví",
                "pepco", "ikea", "jysk",],
            "Doprava a Tankování": ["flix", "regiojet", "tank", "ono", "parkoviště", "parkoviste", "benzina"],
            "Zábava": ["ticketmaster", "ticketportal", "nfctron",],
            "Krása a Zdraví": ["dm", "teta", "rossmann", "drogerie",
                "max", "lékárna", "notino","optik",],
            "Investice, Finance": ["revolut","vklad","investice","investic",],
            "Sport":["sportisimo","decathlon","sport","bazén",],
            "Dluhy kamarádům": ["hencl", "dognerová","süssnerová","minařík",],
        }

    def urci_kategorii(self, vydaj: Vydaj) -> str:
        text = vydaj.popis.lower()
        for kategorie, klicova_slova in self.pravidla.items():
            for slovo in klicova_slova:
                if slovo in text:
                    return kategorie
        return "Ostatní"

class GeminiKategorizace(kategorizace):
    def __init__(self, api_key: str, povolene_kategorie: list[str]):
        self.client = genai.Client(api_key=api_key)
        self.povolene_kategorie = povolene_kategorie

    def urci_kategorii(self, vydaj: Vydaj) -> str:
        vysledky = self.urci_kategorie_hromadne([vydaj])
        return vysledky[0]

    def urci_kategorie_hromadne(self, vydaje: list[Vydaj]) -> list[str]:
        seznam_kategorii = ", ".join(self.povolene_kategorie)
        polozky_text = "\n".join(
            f"{i}: {v.popis}" for i, v in enumerate(vydaje)
        )

        prompt = (
            f"Zařaď následující bankovní výdaje do jedné z těchto kategorií: {seznam_kategorii}. "
            f"Pokud do žádné jednoznačně nepatří, použij 'Ostatní'.\n"
            f"Výdaje:\n{polozky_text}\n\n"
            f"Odpověz POUZE jako čistý JSON slovník, kde klíč je číslo řádku (jako string) "
            f"a hodnota je přesný název kategorie. Nepiš žádný další text ani markdown."
        )

        try:
            odpoved = self.client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
            print("Surová odpověď z Gemini:", odpoved.text)
            cisty_json = odpoved.text.strip().removeprefix("```json").removesuffix("```").strip()
            slovnik_odpovedi = json.loads(cisty_json)
        except Exception as e:
            print(f"Upozornění: Gemini API selhalo ({e}). Položky zůstávají v Ostatní.")
            return ["Ostatní"] * len(vydaje)

        mapa_kategorii = {k.lower(): k for k in self.povolene_kategorie}

        vysledky = []
        for i in range(len(vydaje)):
            kat = str(slovnik_odpovedi.get(str(i), "Ostatní")).strip().lower()
            vysledky.append(mapa_kategorii.get(kat, "Ostatní"))
        return vysledky

class Vizualizator:
    def __init__(self, transakce: list[Transakce]):
        self.transakce = transakce

    def vykresli_mesicni_prehled(self):
        data_po_mesicich = {}

        for t in self.transakce:
            mesic = t.datum.strftime("%Y-%m")
            if mesic not in data_po_mesicich:
                data_po_mesicich[mesic] = {"prijmy": 0.0, "vydaje": 0.0, "prevody": 0.0}

            if isinstance(t, Prijem):
                data_po_mesicich[mesic]["prijmy"] += t.castka
            elif isinstance(t, Vydaj):
                data_po_mesicich[mesic]["vydaje"] += abs(t.castka)
            elif isinstance(t, Prevod) and t.castka > 0:
                data_po_mesicich[mesic]["prevody"] += t.castka

        mesice = sorted(data_po_mesicich.keys())
        prijmy = [data_po_mesicich[m]["prijmy"] for m in mesice]
        vydaje = [data_po_mesicich[m]["vydaje"] for m in mesice]
        prevody = [data_po_mesicich[m]["prevody"] for m in mesice]

        x = range(len(mesice))
        sirka = 0.25

        plt.figure(figsize=(11, 6))
        sloupce_prijmy = plt.bar(
            [i - sirka for i in x], prijmy, width=sirka, label="Příjmy", color="#2ecc71"
        )
        sloupce_vydaje = plt.bar(
            x, vydaje, width=sirka, label="Výdaje", color="#e74c3c"
        )
        sloupce_prevody = plt.bar(
            [i + sirka for i in x], prevody, width=sirka, label="Převody", color="#3498db"
        )

        plt.bar_label(sloupce_prijmy, fmt="%.0f Kč", padding=3, fontsize=8)
        plt.bar_label(sloupce_vydaje, fmt="%.0f Kč", padding=3, fontsize=8)
        plt.bar_label(sloupce_prevody, fmt="%.0f Kč", padding=3, fontsize=8)

        plt.ylabel("Částka (Kč)")
        plt.title("Měsíční přehled příjmů, výdajů a převodů")
        plt.xticks(x, mesice)
        plt.margins(y=0.15)
        plt.legend(frameon=False)
        plt.grid(axis="y", linestyle="--", alpha=0.5)
        plt.tight_layout()

    def vykresli_kategorie_vydaju(self):
        vydaje_kategorie = {}

        for t in self.transakce:
            if isinstance(t, Vydaj):
                vydaje_kategorie[t.kategorie] = (
                    vydaje_kategorie.get(t.kategorie, 0.0) + abs(t.castka)
                )

        serazene = sorted(vydaje_kategorie.items(), key=lambda x: x[1], reverse=True)
        hodnoty = [polozka[1] for polozka in serazene]
        celkem = sum(hodnoty)

        legenda_popisky = [
            f"{kat} ({hodnota:.0f} Kč, {hodnota / celkem * 100:.1f} %)"
            for kat, hodnota in serazene
        ]

        def formatuj_popisek(procento):
            if procento < 4:
                return ""
            castka = procento * celkem / 100.0
            return f"{castka:.0f} Kč\n({procento:.1f}%)"

        plt.figure(figsize=(11, 7))
        plt.pie(
            hodnoty,
            autopct=formatuj_popisek,
            startangle=90,
            counterclock=False,
            pctdistance=0.75,
            textprops={"fontsize": 9},
        )
        plt.legend(
            legenda_popisky,
            title="Kategorie",
            loc="center left",
            bbox_to_anchor=(1, 0.5),
            frameon=False,
        )
        plt.title("Rozložení výdajů podle kategorií")
        plt.axis("equal")
        plt.tight_layout()

    def zobraz_grafy(self):
        self.vykresli_mesicni_prehled()
        self.vykresli_kategorie_vydaju()
        plt.show()

def exportuj_csv(transakce: list[Transakce], cesta_k_souboru: str = "prehled_transakci.csv") -> None:
    hlavicka = ["Typ operace","Datum","Můj účet","Částka","Měna","Protiúčet","Kategorie","Popis"]

    with open(cesta_k_souboru, mode="w", newline="", encoding="utf-8-sig") as soubor:
        zapisovac = csv.writer(soubor, delimiter=";")
        zapisovac.writerow(hlavicka)

        for t in transakce:
            kategorie = t.kategorie if isinstance(t, Vydaj) else "-"
            zapisovac.writerow([
                t.typ_operace(),
                t.datum.strftime("%d.%m.%Y"),
                t.muj_ucet,
                f"{t.castka:.2f}".replace(".", ","),
                t.mena,
                t.protiucet,
                kategorie,
                t.popis,
            ])

def main():
    zdroje = [
        CsobCsvZdroj("data/csob_bezny1.csv"),
        CsobCsvZdroj("data/csob_sporici1.csv"),
        MonetaCsvZdroj("data/moneta_bezny1.csv"),
            ]

    surove = []
    for zdroj in zdroje:
        surove.extend(zdroj.nacti_transakce())

    tridic = TridicTransakci(surove)
    roztridene = tridic.roztrid()
    roztridene.sort(key=lambda t: t.datum)

    kategorizator = KlicovaSlovaKategorizace()
    for t in roztridene:
        if isinstance(t, Vydaj):
            t.kategorie = kategorizator.urci_kategorii(t)

    ostatni_vydaje = [
        t for t in roztridene if isinstance(t, Vydaj) and t.kategorie == "Ostatní"
    ]

    if ostatni_vydaje:
        volba_ai = input(
            f"Nalezeno {len(ostatni_vydaje)} výdajů v kategorii Ostatní. Použít Gemini AI pro jejich zařazení? (a/n): "
        ).strip().lower()

        if volba_ai == "a":
            api_key = input("Zadejte Gemini API klíč: ").strip()
            print("Odesílám výdaje ke kategorizaci do Gemini AI...")
            povolene = list(kategorizator.pravidla.keys())
            ai_kategorizator = GeminiKategorizace(api_key, povolene)

            nove_kategorie = ai_kategorizator.urci_kategorie_hromadne(ostatni_vydaje)
            for vydaj, kat in zip(ostatni_vydaje, nove_kategorie):
                vydaj.kategorie = kat
            print("Kategorizace pomocí AI dokončena.\n")

    for t in roztridene:
        print(t)

    volba_export = input("Chcete výsledky exportovat do CSV souboru? (a/n): ").strip().lower()
    if volba_export == "a":
        nazev_souboru = input("Zadejte název souboru (Enter pro 'prehled_transakci.csv'): ").strip()
        if not nazev_souboru:
            nazev_souboru = "prehled_transakci.csv"
        elif not nazev_souboru.endswith(".csv"):
            nazev_souboru += ".csv"

        exportuj_csv(roztridene, nazev_souboru)
        print(f"Data byla úspěšně uložena do souboru '{nazev_souboru}'.")

    grafy = Vizualizator(roztridene)
    grafy.zobraz_grafy()

if __name__ == "__main__":
    main()