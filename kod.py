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