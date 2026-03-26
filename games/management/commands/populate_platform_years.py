"""
Management command to populate platform year_start and year_end fields.

Usage:
    python manage.py populate_platform_years
"""

from django.core.management.base import BaseCommand
from games.models import Platform


PLATFORM_YEAR_RANGES = {
    # Nintendo
    "NES": (1983, 1995),
    "FDS": (1986, 1992),
    "SNES": (1990, 2000),
    "N64": (1996, 2002),
    "GC": (2001, 2007),
    "Wii": (2006, 2013),
    "WiiU": (2012, 2017),
    "SW": (2017, None),
    "SW2": (2025, None),
    "GB": (1989, 2001),
    "GBC": (1998, 2003),
    "GBA": (2001, 2008),
    "DS": (2004, 2014),
    "3DS": (2011, 2020),
    # PlayStation
    "PS": (1994, 2006),
    "PS2": (2000, 2013),
    "PS3": (2006, 2017),
    "PS4": (2013, 2025),
    "PS5": (2020, None),
    "PSVR": (2016, 2023),
    "PSP": (2004, 2014),
    "PSV": (2011, 2019),
    # Xbox
    "Xbox": (2001, 2009),
    "X360": (2005, 2016),
    "XB1": (2013, 2020),
    "XBXS": (2020, None),
    # Sega
    "SMS": (1985, 1996),
    "GEN": (1988, 1998),
    "SCD": (1991, 1996),
    "SAT": (1994, 2000),
    "DC": (1998, 2001),
    "GG": (1990, 1997),
    # PC
    "WIN": (1985, None),
    "DOS": (1981, 2000),
    "LIN": (1991, None),
    "MAC": (1984, None),
    # Arcade+
    "ARC": (1971, None),
    "AND": (2008, None),
    "iOS": (2007, None),
    "LMD": (1997, 2012),
    "VR": (2016, None),
    "BR": (2004, None),
    # Retro Consoles
    "A26": (1977, 1992),
    "A52": (1982, 1984),
    "A78": (1986, 1992),
    "INTV": (1979, 1990),
    "CV": (1982, 1985),
    "TG16": (1987, 1999),
    "3DO": (1993, 1996),
    "NG": (1990, 2004),
    "JAG": (1993, 1996),
    "LYNX": (1989, 1995),
    "NGP": (1998, 2001),
    "WS": (1999, 2003),
    # Microcomputers
    "C64": (1982, 1994),
    "AMI": (1985, 1996),
    "CD32": (1993, 1994),
    "MSX": (1983, 1995),
    "CPC": (1984, 1990),
    "ZXS": (1982, 1992),
    "AST": (1985, 1993),
    "BBCM": (1981, 1994),
    "PC88": (1981, 1991),
    "PC98": (1982, 2000),
    "FMT": (1989, 1997),
    "FM7": (1982, 1988),
    "SX1": (1982, 1988),
    "T80": (1977, 1991),
    "TCC": (1980, 1991),
    "VC20": (1980, 1985),
    "A8": (1979, 1992),
    "A2": (1977, 1993),
    "D32": (1982, 1987),  # Dragon 32/64
    "GW": (1980, 1991),  # Game & Watch
    "MIC": (1973, None),  # Generic microcomputer catch-all
    "TT": (1982, 1985),  # Tomy Tutor / Pyuuta
    "VECT": (1982, 1984),  # Vectrex
    # Additional platforms
    "ARCH": (1987, 1995),  # Acorn Archimedes
    "PDP": (1959, 1997),  # DEC PDP (PDP-1 through PDP-11)
    "E60": (1978, 1991),  # Electronika 60 (Soviet, original Tetris platform)
    "HP21": (1966, 1990),  # HP 2100 series
}


class Command(BaseCommand):
    help = "Populate year_start and year_end for all platforms"

    def handle(self, *args, **options):
        updated_count = 0
        missing_count = 0

        self.stdout.write("Populating platform year ranges...")

        for platform in Platform.objects.all():
            if platform.code in PLATFORM_YEAR_RANGES:
                year_start, year_end = PLATFORM_YEAR_RANGES[platform.code]
                platform.year_start = year_start
                platform.year_end = year_end
                platform.save(update_fields=["year_start", "year_end"])
                updated_count += 1
                end_str = year_end if year_end else "present"
                self.stdout.write(
                    f"  ✓ {platform.code} ({platform.name}): {year_start}-{end_str}"
                )
            else:
                missing_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠ {platform.code} ({platform.name}): No year data available"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Updated {updated_count} platforms, "
                f"{missing_count} missing year data"
            )
        )
