import csv
import matplotlib.pyplot as plt
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

#načtení dat-nadřazená třída
class ZdrojDat(ABC):
    @abstractmethod
    def nacti_transakce(self) -> list[SurovaTransakce]:
        pass

#načtení dat z csv soubroů
class CsvZdrojDat(ZdrojDat, ABC):
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
#
#DOPLNIT VÍCE KLÍČOVÝCH SLOV A KATEGORIÍÍÍ!!
#
class KlicovaSlovaKategorizace(kategorizace):
    def __init__(self):
        self.pravidla = {
            "Potraviny": ["albert", "lidl"],
            "Bydlení": ["nájem", "najem", "elektřina", "voda"],
            "Nákupy": ["alza", "elektroniky", "oblečení"],
        }

    def urci_kategorii(self, vydaj: Vydaj) -> str:
        text = vydaj.popis.lower()
        for kategorie, klicova_slova in self.pravidla.items():
            for slovo in klicova_slova:
                if slovo in text:
                    return kategorie
        return "Ostatní"
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

        plt.figure(figsize=(10, 6))
        plt.bar([i - sirka for i in x], prijmy, width=sirka, label="Příjmy", color="#2ecc71")
        plt.bar(x, vydaje, width=sirka, label="Výdaje", color="#e74c3c")
        plt.bar([i + sirka for i in x], prevody, width=sirka, label="Převody", color="#3498db")

        plt.xlabel("Měsíc")
        plt.ylabel("Částka (CZK)")
        plt.title("Měsíční přehled příjmů, výdajů a převodů")
        plt.xticks(x, mesice)
        plt.legend()
        plt.grid(axis="y", linestyle="--", alpha=0.5)
        plt.tight_layout()

    def vykresli_kategorie_vydaju(self):
        vydaje_kategorie = {}

        for t in self.transakce:
            if isinstance(t, Vydaj):
                vydaje_kategorie[t.kategorie] = (
                    vydaje_kategorie.get(t.kategorie, 0.0) + abs(t.castka)
                )

        kategorie = list(vydaje_kategorie.keys())
        hodnoty = list(vydaje_kategorie.values())

        plt.figure(figsize=(8, 8))
        plt.pie(
            hodnoty,
            labels=kategorie,
            autopct="%1.1f%%",
            startangle=90,
        )
        plt.title("Rozložení výdajů podle kategorií")
        plt.axis("equal")
        plt.tight_layout()
        
    def zobraz_grafy(self):
        self.vykresli_mesicni_prehled()
        self.vykresli_kategorie_vydaju()
        plt.show()

def main():
    zdroje = [
        CsobCsvZdroj("data/csob_bezny.csv"),
        CsobCsvZdroj("data/csob_sporici.csv"),
        MonetaCsvZdroj("data/moneta_bezny.csv"),
    ]

    surove = []
    for zdroj in zdroje:
        surove.extend(zdroj.nacti_transakce())

    tridic = TridicTransakci(surove)
    roztridene = tridic.roztrid()

    kategorizator = KlicovaSlovaKategorizace()
    for t in roztridene:
        if isinstance(t, Vydaj):
            t.kategorie = kategorizator.urci_kategorii(t)

    for t in roztridene:
        print(t)

    grafy = Vizualizator(roztridene)
    grafy.zobraz_grafy()

if __name__ == "__main__":
    main()