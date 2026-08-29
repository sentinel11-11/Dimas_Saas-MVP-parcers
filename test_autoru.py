import asyncio
from app.parsers.autoru.autoru_parser import AutoRuParser

async def test():
    p = AutoRuParser(headless=True)
    cars = await p.search({'brand': 'audi', 'model': 'q3'}, limit=5)
    print(f'Auto.ru: found {len(cars)} cars')
    await p.close()
    return len(cars)

if __name__ == "__main__":
    result = asyncio.run(test())
    print(f"Test completed: {result} cars found")
