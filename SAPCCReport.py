import openpyxl as pyxl
from openpyxl.worksheet.worksheet import Worksheet
from abc import ABC
from dataclasses import dataclass
from pathlib import Path

''' An absctract class to represent a SAP CC Excel export report'''
PRIMARY_SHEETNAME:str = "CommerceProduct"

@dataclass
class SAPCCReportFile:
    report_path:Path
    report_workbook:pyxl.Workbook

def reprt_file_from_path(report_path: Path) -> SAPCCReportFile:
    wb = pyxl.load_workbook(report_path.as_posix())
    return SAPCCReportFile(report_path, wb)

class InvalidSAPCCReport(Exception):
    pass

class SAPCCExportReport(ABC):
    
    def __init__(self, report_file: SAPCCReportFile):
        self._report_file = report_file


    @property
    def wb(self) -> pyxl.Workbook:
        return self._report_file.report_workbook
    
    @property
    def data_starting_row(self) -> int:
        return 4
    
    def _get_ws(self, report_file:SAPCCReportFile, sheetname:str=PRIMARY_SHEETNAME) -> Worksheet:
        return report_file.report_workbook[sheetname]
    

    


