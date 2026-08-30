"""Марки для подсказок. Любая марка/модель вводится текстом — URL строится из slug."""

ALL_BRANDS = [
    "acura", "alfa romeo", "aston martin", "audi", "baic", "bentley", "bmw",
    "brilliance", "bugatti", "buick", "byd", "cadillac", "changan", "chery",
    "chevrolet", "chrysler", "citroen", "cupra", "dacia", "daewoo", "daihatsu",
    "datsun", "dodge", "dongfeng", "exeed", "faw", "ferrari", "fiat", "ford",
    "foton", "gac", "gaz", "geely", "genesis", "gmc", "great wall", "haval",
    "honda", "hongqi", "hummer", "hyundai", "infiniti", "isuzu", "jac", "jaguar",
    "jaecoo", "jeep", "jetour", "kia", "lada", "lamborghini", "lancia",
    "land rover", "lexus", "lifan", "lincoln", "lixiang", "lotus", "maserati",
    "maybach", "mazda", "mclaren", "mercedes", "mini", "mitsubishi", "moskvich",
    "nissan", "omoda", "opel", "peugeot", "plymouth", "polestar", "pontiac",
    "porsche", "ram", "ravon", "renault", "rolls-royce", "rover", "saab",
    "seat", "skoda", "smart", "ssangyong", "subaru", "suzuki", "tank", "tesla",
    "toyota", "uaz", "volkswagen", "volvo", "voyah", "wey", "zeekr",
]

POPULAR_MODELS = {
    "audi": ["A3", "A4", "A5", "A6", "A8", "Q3", "Q5", "Q7", "Q8", "e-tron"],
    "bmw": ["3 серия", "5 серия", "7 серия", "X1", "X3", "X5", "X6", "X7"],
    "mercedes": ["C-Class", "E-Class", "S-Class", "GLC", "GLE", "GLS", "G-Class"],
    "toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Highlander", "Prius"],
    "kia": ["Rio", "Ceed", "Cerato", "K5", "Sportage", "Sorento", "Optima"],
    "hyundai": ["Solaris", "Elantra", "Sonata", "Tucson", "Santa Fe", "Creta"],
    "volkswagen": ["Polo", "Golf", "Passat", "Tiguan", "Touareg"],
    "lada": ["Granta", "Vesta", "Niva", "Largus", "XRAY"],
    "haval": ["Jolion", "F7", "Dargo", "H9"],
    "geely": ["Coolray", "Atlas", "Monjaro", "Okavango", "Preface"],
}


def slug_part(value: str) -> str:
    v = (value or "").strip().lower().replace(" ", "")
    return v
