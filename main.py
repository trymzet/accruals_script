"""
Author: Michal Zawadzki, michalmzawadzki@gmail.com
Run the script from the same directory as WD report and master file
"""

import pandas as pd
import openpyxl
from subprocess import call
from os import remove

WD_report_name = "EXP031-RPT-Process-Accruals_with_Expense_Report.xlsx"
WD2_report_name = "EXP032-RPT-Process-Accruals-_No_Expense.xlsx"
AP_account = 25702400  # the account from which the money will flow
generic_GL_account = 46540000


def generate_vbs_script():
    # this VBS script converts XLSX files to CSV format for faster processing
    vbscript = """if WScript.Arguments.Count < 3 Then
        WScript.Echo "Please specify the source and the destination files. Usage: ExcelToCsv <xls/xlsx source file> <csv destination file> <worksheet number (starts at 1)>"
        Wscript.Quit
    End If

    csv_format = 6

    Set objFSO = CreateObject("Scripting.FileSystemObject")

    src_file = objFSO.GetAbsolutePathName(Wscript.Arguments.Item(0))
    dest_file = objFSO.GetAbsolutePathName(WScript.Arguments.Item(1))
    worksheet_number = CInt(WScript.Arguments.Item(2))

    Dim oExcel
    Set oExcel = CreateObject("Excel.Application")

    Dim oBook   
    Set oBook = oExcel.Workbooks.Open(src_file)
    oBook.Worksheets(worksheet_number).Activate

    oBook.SaveAs dest_file, csv_format

    oBook.Close False
    oExcel.Quit
    """
    try:
        with open("ExcelToCsv.vbs", "wb") as f:
            f.write(vbscript.encode("utf-8"))
    except:
        print("VBS script for converting xlsx files to csv could not be generated.")


def load_csv(xlsx_file_name, has_sheets=False, skiprows=None, usecols=None):
    # this function maps the generate_vbs_script() function to the input XLSX file
    if has_sheets:
        # sheet numbers to use; using the first three and I don't know how to retrieve no of sheets, hence the fixed numbers
        sheets = map(str, range(1, 4))
        sheet_dataframes = []
        for sheet in sheets:
            csv_file_name = "../Script/{}{}".format(sheet, ".csv")
            call(["cscript.exe", "../Script/ExcelToCsv.vbs", xlsx_file_name, csv_file_name, sheet, r"//B"])
            try:
                sheet_dataframe = pd.read_csv(csv_file_name, encoding="latin-1", engine="c", usecols=usecols)
            except:
                print("Sheets could not be converted to CSV format.")
            sheet_dataframes.append(sheet_dataframe)
        return tuple(sheet_dataframes)
    else:
        csv_file_name = "{}{}".format(xlsx_file_name[:-4], "csv")
        # //B is for batch mode; this is to avoid spam on the console :)
        call(["cscript.exe", "../Script/ExcelToCsv.vbs", xlsx_file_name, csv_file_name, str(1), r"//B"])
        if skiprows:
            try:
                data = pd.read_csv(csv_file_name, skiprows=skiprows, encoding="latin-1", engine="c", usecols=usecols)

            except:
                print("Something went wrong... make sure report names weren't changed or debug the load_csv function")
        else:
            try:
                    data = pd.read_csv(csv_file_name, encoding="latin-1", engine="c", usecols=usecols)
            except:
                print("Something went wrong... make sure report names weren't changed or debug the load_csv function")
        return data


"""
def load_workbook(file_name, sheetname=None, skiprows=None):
    if skiprows:
        try:
            wb = pd.read_excel(file_name, skiprows=skiprows, na_values="")
        except FileNotFoundError:
            print("File {} not found in current directory.".format(file_name))
    if sheetname:
        try:
            wb = pd.read_excel(file_name, sheetname=sheetname, na_values="")
        except:
            print("Sheet {} has been renamed or deleted".format(sheetname))
    else:
        try:
            wb = pd.read_excel(file_name, na_values="")
        except:
            print("File {} not found in current directory.".format(file_name))
    return wb
"""


def load_all():
    master_file_name = "WD_Accruals_Master.xlsm"
    file_names = [WD_report_name, WD2_report_name, master_file_name]
    dataframes = []
    WD1_required_cols = ["Entity Code", "Cost Center", "Expense Report Number", "Expense Item", "Net Amount LC"]
    WD2_required_cols = ["Transaction ID", "Billing Amount", "Currency", "Report Cost Location"]

    # the script will be used by load_csv() to convert XLSX to CSV for faster processing
    generate_vbs_script()

    for file_name in file_names:
        if file_name == WD_report_name:
            df = load_csv(file_name, skiprows=[0], usecols=WD1_required_cols)
        elif file_name == WD2_report_name:
            df = load_csv(file_name, usecols=WD2_required_cols)
        else:
            cc_to_ba, accounts, JE_template = load_csv(file_name, has_sheets=True)
            dataframes.extend([cc_to_ba, accounts, JE_template])
            return dataframes
        dataframes.append(df)
    return dataframes


def collect_garbage():
    # remove no longer needed files
    WD_report_byproduct = "{}{}".format(WD_report_name[:-5], ".csv")
    WD2_report_byproduct = "{}{}".format(WD2_report_name[:-5], ".csv")
    excel_to_csv_macro_byproducts = ["1.csv", "2.csv", "3.csv", WD_report_byproduct, WD2_report_byproduct]
    for byproduct in excel_to_csv_macro_byproducts:
        remove(byproduct)
    remove("ExcelToCsv.vbs")


def initial_cleanup():
    # TODO: deal with scientific-notation-like business areas converting to sci-notation
    global WD_report, WD2_report

    collect_garbage()

    # remove rows with total amount 0 or less / unfortunately, pandas nor Python are able to convert amounts in the format:
    # 123,456.00 to float, hence need to either use localization (bad idea as the process is WW), or use below workaround
    try:
        WD_report["Net Amount LC"] = WD_report["Net Amount LC"].apply(lambda x: x.replace(",", "") if type(x) != float else x)
    except:
        pass
    WD_report["Net Amount LC"] = WD_report["Net Amount LC"].map(float)
    WD_report = WD_report[WD_report["Net Amount LC"] > 0]
    try:
        WD2_report["Billing Amount"] = WD2_report["Billing Amount"].apply(lambda x: x.replace(",", "") if type(x) != float else x)
    except:
        pass
    WD2_report = WD2_report[WD2_report["Billing Amount"].apply(lambda x: "(" not in x)]
    WD2_report["Billing Amount"] = WD2_report["Billing Amount"].map(float)
    # delete any rows that don't have a cost center specified, as this data is critical to generating an accrual
    WD_report.dropna(subset=["Cost Center"], inplace=True)
    WD2_report.dropna(subset=["Report Cost Location"], inplace=True)
    # delete the duplicate cost centers/descriptions inside Cost Center column
    WD_report["Cost Center"] = WD_report["Cost Center"].astype("str").map(lambda x: x.split()[0])
    WD2_report["Report Cost Location"] = WD2_report["Report Cost Location"].astype("str").map(lambda x: x.split()[0])
    # add cc column as it will be used by generate_csv()
    WD2_report["Company code"] = WD2_report["Report Cost Location"].apply(lambda x: x[:4])


def vlookup(report, what, left_on, right_on):
    merged = report.merge(what, left_on=left_on, right_on=right_on, how="left")
    return merged


def run_vlookups():
    global WD_report, WD2_report
    accounts = pd.DataFrame(accounts_file["Account"]).astype(int)
    master_data_to_join = master_data_file[["Business Area", "Profit Center", "MRU", "Functional Area"]]

    WD_report = vlookup(WD_report, accounts, left_on=[WD_report["Expense Item"], WD_report["Entity Code"]], right_on=[accounts_file["Expense Item name"], accounts_file["Subsidiary"]])
    # the account number is provided separately for each country. However, all countries have the same account for a given category, so we need to remove these duplicate rows.
    # in case any country has a separate account for a given category in the future, the script will still work
    WD_report = vlookup(WD_report, master_data_to_join, WD_report["Cost Center"], master_data_file["Cost Center"])
    WD2_report = vlookup(WD2_report, master_data_to_join, WD2_report["Report Cost Location"], master_data_file["Cost Center"])


def final_cleanup():
    global WD_report
    global accounts_file
    travel_journal_item_account = 46540000
    company_celebration_account = 46900000
    german_debit_account = 46920000

    # add vlookup exceptions
    no_of_items = WD_report.shape[0]
    for row_index in range(no_of_items):
        category = str(WD_report["Expense Item"].iloc[row_index])  # for some reason this column is loaded as float, hence the str()
        if "Travel Journal Item" in category:
            WD_report.loc[row_index, "Acc#"] = travel_journal_item_account
            # WD_report.set_value(index, "Acc#", travel_journal_item_account)
        if "Company Celebration" in category:
            # WD_report.set_value(index, "Acc#", company_celebration_account)
            WD_report.loc[row_index, "Acc#"] = company_celebration_account

    # this is to stop Excel from reading e.g. 2E00 as a number in scientific notation
    WD_report["Business Area"] = WD_report["Business Area"].map(str)

    # note that this also overrides the above two exceptions, which are changed to the german account
    WD_report.loc[WD_report["Entity Code"] == "DESA", "Acc#"] = german_debit_account

    # ensure that account number is provided, and that it is an integer
    try:
        WD_report["Acc#"] = WD_report["Acc#"].map(int)
    except:
        # this means that some account numbers were not found for a company code-category combination -> use an account
        # for the same category, but another company code (all CCs should use the same account)
        lines_with_missing_account = WD_report[WD_report["Acc#"].isnull()]
        # remove duplicate categories, effectively leaving the first found acc # for a given category, which is what is going to be assigned for missing values
        deduplicated_accounts_file = accounts_file.drop_duplicates(subset=["Expense Item name"])
        accounts = pd.DataFrame(deduplicated_accounts_file["Account"])
        # dropping Account column so that merge does not produce useless new columns
        deduplicated_accounts_file.drop("Account", axis=1, inplace=True)
        lines_with_missing_account.drop("Acc#", axis=1, inplace=True)
        merged = lines_with_missing_account.merge(accounts, left_on=lines_with_missing_account["Expense Item"],
                                                  right_on=deduplicated_accounts_file["Expense Item name"], how="left")
        print(lines_with_missing_account.columns)
        print(merged.columns)

    # the accounts vlookup finds all possible accounts for a category, so this also needs to be filtered by subsidiary
    duplicates = WD_report.duplicated(subset=["Expense Report Number", "Expense Item", "Net Amount LC"])
    print(duplicates[duplicates].shape[0])
    duplicates = WD_report[duplicates]
    duplicates.to_csv("duplicates.csv")

    #WD_report.drop_duplicates(subset=["Expense Report Number", "Expense Item", "Net Amount LC"], inplace=True)


WD_report, WD2_report, master_data_file, accounts_file, JE_template_file = load_all()
print("All files loaded :)")
initial_cleanup()
print("Data cleaned :)")
run_vlookups()
final_cleanup()


# TODO: if the account / profit center / ba is not found, add those lines to a "not found" file for a manual check


WD_report["Checksum"] = WD_report["Profit Center"].astype(str) + WD_report["Business Area"]
WD2_report["Checksum"] = WD2_report["Profit Center"].astype(str) + WD2_report["Business Area"]

temp = "../Script/Result/" + WD_report_name
temp2 = "../Script/Result/" + WD2_report_name

with pd.ExcelWriter(temp) as writer:
    WD_report.to_excel(writer, engine="openpyxl", index=False)
with pd.ExcelWriter(temp2) as writer2:
    WD2_report.to_excel(writer2, engine="openpyxl", index=False)
