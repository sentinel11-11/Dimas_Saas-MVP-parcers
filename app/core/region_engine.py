class RegionEngine:

    REGION_COEFFICIENTS = {

        "москва": 1.15,
        "московская область": 1.1,

        "спб": 1.1,

        "екатеринбург": 1.05,

        "краснодар": 1.0,

        "омск": 0.9,
        "новосибирск": 0.95,
        "саратов": 0.88
    }

    @classmethod
    def get_coef(cls, region):

        if not region:
            return 1.0

        region = region.lower()

        return cls.REGION_COEFFICIENTS.get(region, 1.0)