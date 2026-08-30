import csv
import os
from datetime import datetime
from typing import List, Any
from loguru import logger


class DataExporter:
    """Экспорт данных в CSV и Excel форматы"""
    
    @staticmethod
    def export_to_csv(cars: List[Any], filename: str = None) -> str:
        """Экспорт списка автомобилей в CSV файл"""
        if not filename:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"data/exports/cars_{timestamp}.csv"
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        fieldnames = [
            'url', 'title', 'platform', 'brand', 'model', 'price', 'year',
            'mileage', 'engine_volume', 'horsepower', 'transmission', 'drive',
            'body_type', 'owners', 'accidents', 'pts', 'region',
            'market_score', 'market_price', 'liquidity_score', 
            'probability_good_deal', 'market_deviation'
        ]
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
                writer.writeheader()
                
                for car in cars:
                    if isinstance(car, dict):
                        row = {field: car.get(field, car.get("probability") if field == "probability_good_deal" else "") for field in fieldnames}
                        row["probability_good_deal"] = car.get("probability", car.get("probability_good_deal", ""))
                    else:
                        row = {field: getattr(car, field, "") for field in fieldnames}
                    writer.writerow(row)
            
            logger.info(f"CSV exported: {filename} ({len(cars)} records)")
            return filename
            
        except Exception as e:
            logger.error(f"CSV export error: {e}")
            return ""
    
    @staticmethod
    def export_to_excel(cars: List[Any], filename: str = None) -> str:
        """Экспорт списка автомобилей в Excel файл"""
        try:
            import pandas as pd
            
            if not filename:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = f"data/exports/cars_{timestamp}.xlsx"
            
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            data = []
            for car in cars:
                row = {
                    'URL': car.url,
                    'Title': car.title,
                    'Platform': car.platform,
                    'Brand': car.brand,
                    'Model': car.model,
                    'Price (₽)': car.price,
                    'Year': car.year,
                    'Mileage (км)': car.mileage,
                    'Engine (L)': car.engine_volume,
                    'Horsepower': car.horsepower,
                    'Transmission': car.transmission,
                    'Drive': car.drive,
                    'Body Type': car.body_type,
                    'Owners': car.owners,
                    'Accidents': car.accidents,
                    'PTS': car.pts,
                    'Region': car.region,
                    'Market Score': round(car.market_score, 2),
                    'Market Price (₽)': round(car.market_price, 2) if car.market_price else 0,
                    'Liquidity Score': round(car.liquidity_score, 2),
                    'Deal Probability': round(car.probability_good_deal, 2),
                    'Market Deviation (%)': round(car.market_deviation, 2) if hasattr(car, 'market_deviation') and car.market_deviation else 0
                }
                data.append(row)
            
            df = pd.DataFrame(data)
            
            # Сортировка по вероятности выгодной сделки
            df = df.sort_values('Deal Probability', ascending=False)
            
            # Сохранение в Excel
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Car Deals')
                
                # Автоширина колонок
                worksheet = writer.sheets['Car Deals']
                for column in worksheet.columns:
                    max_length = max(len(str(cell.value)) if cell.value else 10 for cell in column)
                    col_letter = column[0].column_letter
                    worksheet.column_dimensions[col_letter].width = min(max_length + 2, 25)
            
            logger.info(f"Excel exported: {filename} ({len(cars)} records)")
            return filename
            
        except ImportError:
            logger.error("pandas/openpyxl not installed. Install with: pip install pandas openpyxl")
            return ""
        except Exception as e:
            logger.error(f"Excel export error: {e}")
            return ""