import csv
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

