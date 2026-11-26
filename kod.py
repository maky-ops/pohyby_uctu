import csv
import matplotlib.pyplot as plt
import json
from google import genai
from abc import ABC, abstractmethod
from datetime import date, datetime
from dataclasses import dataclass

@dataclass
class Transakce:
    id_transakce: str
    muj_ucet: str
    datum: date
    castka: float
    mena: str
    protiucet: str
    popis: str
    typ: str = "NEURČENO"
    kategorie: str = "-"

    def __str__(self) -> str:
        zaklad = (
            f"[{self.typ:^6}] [{self.datum.strftime('%d.%m.%Y')}] "
            f"Účet: {self.muj_ucet} | Částka: {self.castka:>9.2f} {self.mena} | "
            f"Protiúčet: {self.protiucet:<14} | {self.popis}"
        )
        return f"{zaklad} | Kategorie: {self.kategorie}" if self.typ == "VÝDAJ" else zaklad

#načtení dat z csv soubroů
class CsvZdrojDat(ABC):
    def __init__(self, cesta_k_souboru: str):
        self.cesta_k_souboru = cesta_k_souboru

    @abstractmethod
    def _zpracuj_radek(self, radek: dict[str, str]) -> Transakce:
        pass

    def nacti_transakce(self) -> list[Transakce]:
        with open(self.cesta_k_souboru, mode="r", encoding="utf-8-sig") as soubor:
            precti = csv.DictReader(soubor, delimiter=";")
            return [self._zpracuj_radek(radek) for radek in precti]
    
    def _preved_castku(self, text_castky: str) -> float:
        return float(text_castky.replace(" ", "").replace(",", "."))

    def _spoj_ucet(self, cislo: str, kod_banky: str) -> str:
        cislo = cislo.strip()
        kod_banky = kod_banky.strip()
        if cislo and kod_banky:
            return f"{cislo}/{kod_banky}"
        return cislo if cislo else "Neznámý účet"

#přizpůsobení na ČSOB
class CsobCsvZdroj(CsvZdrojDat):
    def _zpracuj_radek(self, radek: dict[str,str]) ->Transakce:    
        return Transakce(
            id_transakce=radek["ID transakce"].strip(),
            muj_ucet=radek["číslo účtu"].strip(),
            datum=datetime.strptime(radek["datum zaúčtování"].strip(), "%d.%m.%Y").date(),
            castka=self._preved_castku(radek["částka"]),
            mena=radek["měna"].strip(),
            protiucet=self._spoj_ucet(radek["číslo protiúčtu"], radek["kód banky protiúčtu"]),
            popis=(radek["zpráva"].strip() or radek["jméno protistrany"].strip()),
        )

#přizpůsobení na Monetu
class MonetaCsvZdroj(CsvZdrojDat):
    def _zpracuj_radek(self, radek: dict[str,str]) ->Transakce:    
        return Transakce(
            id_transakce=radek["Bankovní reference"].strip(),
            muj_ucet=radek["Číslo účtu"].strip(),
            datum=datetime.strptime(radek["Odesláno"].strip(), "%d.%m.%Y").date(),
            castka=self._preved_castku(radek["Částka"]),
            mena=radek["Měna"].strip(),
            protiucet=self._spoj_ucet(radek["Číslo protiúčtu"], radek["Banka protiúčtu"]),
            popis=(radek["Zpráva pro příjemce"].strip() or radek["Popis platby"].strip() 
                or radek["Název účtu příjemce"].strip()),
        )

def roztrid_transakce (transakce: list[Transakce]) -> None:
    moje_ucty = {t.muj_ucet for t in transakce}
    for t in transakce:
        if t.protiucet in moje_ucty:
            t.typ = "PŘEVOD"
        elif t.castka > 0:
            t.typ = "PŘÍJEM"
        else:
            t.typ = "VÝDAJ"
            t.kategorie = "Nezařazeno"

class KlicovaSlovaKategorizace:
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

    def urci_kategorii(self, vydaj: Transakce) -> str:
        text = vydaj.popis.lower()
        for kategorie, klicova_slova in self.pravidla.items():
            for slovo in klicova_slova:
                if slovo in text:
                    return kategorie
        return "Ostatní"

class GeminiKategorizace:
    def __init__(self, api_key: str, povolene_kategorie: list[str]):
        self.client = genai.Client(api_key=api_key)
        self.povolene_kategorie = povolene_kategorie

    def urci_kategorie_hromadne(self, vydaje: list[Transakce]) -> list[str]:
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

            if t.typ == "PŘÍJEM":
                 data_po_mesicich[mesic]["prijmy"] += t.castka
            elif t.typ == "VÝDAJ":
                data_po_mesicich[mesic]["vydaje"] += abs(t.castka)
            elif t.typ == "PŘEVOD" and t.castka > 0:
                data_po_mesicich[mesic]["prevody"] += t.castka

        mesice = sorted(data_po_mesicich.keys())
        prijmy = [data_po_mesicich[m]["prijmy"] for m in mesice]
        vydaje = [data_po_mesicich[m]["vydaje"] for m in mesice]
        prevody = [data_po_mesicich[m]["prevody"] for m in mesice]

        x = range(len(mesice))
        sirka = 0.25

        plt.figure(figsize=(11, 6))
        sloupce_prijmy = plt.bar(
            [i - sirka for i in x], prijmy, width=sirka, label="Příjmy", color="#2ecc71")
        sloupce_vydaje = plt.bar(
            x, vydaje, width=sirka, label="Výdaje", color="#e74c3c")
        sloupce_prevody = plt.bar(
            [i + sirka for i in x], prevody, width=sirka, label="Převody", color="#3498db")

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
            if t.typ == "VÝDAJ":
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
            zapisovac.writerow([
                t.typ,
                t.datum.strftime("%d.%m.%Y"),
                t.muj_ucet,
                f"{t.castka:.2f}".replace(".", ","),
                t.mena,
                t.protiucet,
                t.kategorie,
                t.popis,
            ])

def main():
    zdroje = [
        CsobCsvZdroj("data/csob_bezny1.csv"),
        CsobCsvZdroj("data/csob_sporici1.csv"),
        MonetaCsvZdroj("data/moneta_bezny1.csv"),
            ]

    roztridene = []
    for zdroj in zdroje:
        roztridene.extend(zdroj.nacti_transakce())

    roztrid_transakce(roztridene)
    roztridene.sort(key=lambda t: t.datum)

    kategorizator = KlicovaSlovaKategorizace()
    for t in roztridene:
        if t.typ == "VÝDAJ":
            t.kategorie = kategorizator.urci_kategorii(t)

    ostatni_vydaje = [
        t for t in roztridene if t.typ == "VÝDAJ" and t.kategorie == "Ostatní"
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