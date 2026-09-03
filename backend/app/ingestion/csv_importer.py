from fastapi import UploadFile
import pandas as pd
from typing import Any, Type
from pydantic import BaseModel, ValidationError
import io
from .validators import ImportResult
import numpy as np

class CSVImporter:
    """Importer for CSV data files."""

    @staticmethod
    def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Replace NaNs and NaTs with None for Pydantic compatibility."""
        df = df.replace({np.nan: None})
        return df

    async def import_csv(self, file: UploadFile, schema: Type[BaseModel]) -> tuple[list[BaseModel], ImportResult]:
        """
        Reads a CSV file, parses each row according to the given Pydantic schema,
        and collects validation results.
        Returns a tuple of (valid_records, ImportResult).
        """
        result = ImportResult()
        
        try:
            content = await file.read()
            df = pd.read_csv(io.BytesIO(content))
        except Exception as e:
            result.validation_errors.append({"row": 0, "error": f"Failed to parse CSV: {str(e)}"})
            return [], result
            
        df = self._clean_dataframe(df)
        records = df.to_dict(orient="records")
        result.records_received = len(records)
        
        valid_records = []
        
        for index, row in enumerate(records):
            try:
                valid_record = schema.model_validate(row)
                valid_records.append(valid_record)
                result.records_accepted += 1
            except ValidationError as e:
                result.records_rejected += 1
                result.validation_errors.append({
                    "row": index + 1,
                    "errors": e.errors(),
                    "data": row
                })
        
        return valid_records, result
