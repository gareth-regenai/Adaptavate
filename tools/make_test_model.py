"""
make_test_workbook.py

Builds a stand-in for Adaptavate's real workbook so the wrapper can be built and
tested before their file arrives. Structure mirrors what we expect: an Inputs
sheet, a Calculations sheet holding the "secret" formulas, and an Outputs sheet.

Named ranges are used for every input and output cell. This is deliberate and is
the thing we must ask Adaptavate to add to their own workbook.
"""
import pathlib

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import absolute_coordinate, quote_sheetname
from openpyxl.workbook.defined_name import DefinedName

wb = openpyxl.Workbook()

# ----------------------------------------------------------------------------
# SHEET 1: Inputs. The eight values the partner supplies via the web form.
# ----------------------------------------------------------------------------
ws_in = wb.active
ws_in.title = "Inputs"
ws_in["A1"] = "INPUT"
ws_in["B1"] = "VALUE"
ws_in["C1"] = "UNIT"
for c in ("A1", "B1", "C1"):
    ws_in[c].font = Font(bold=True)

inputs = [
    ("Feedstock carbon factor", 1.00, "multiplier",      "in_feedstock_carbon"),
    ("Feedstock yield factor",  1.00, "multiplier",      "in_feedstock_yield"),
    ("Feedstock delivered cost", 180, "GBP/tonne",       "in_feedstock_cost"),
    ("Annual plant capacity", 5000000, "m2/yr",          "in_plant_capacity"),
    ("Current gas consumption",  9.5, "kWh/m2",          "in_gas_consumption"),
    ("Line conversion level",     40, "percent",         "in_line_conversion"),
    ("Biochar inclusion rate",    15, "percent",         "in_biochar_rate"),
    ("Carbon credit price",      120, "GBP/tCO2e",       "in_carbon_price"),
    ("Credit mode multiplier",  1.00, "multiplier",      "in_credit_multiplier"),
]
for i, (label, val, unit, name) in enumerate(inputs, start=2):
    ws_in[f"A{i}"] = label
    ws_in[f"B{i}"] = val
    ws_in[f"C{i}"] = unit
    ref = f"{quote_sheetname(ws_in.title)}!{absolute_coordinate(f'B{i}')}"
    wb.defined_names.add(DefinedName(name, attr_text=ref))

ws_in.column_dimensions["A"].width = 28
ws_in.column_dimensions["C"].width = 14

# ----------------------------------------------------------------------------
# SHEET 2: Calculations. Stands in for Adaptavate's proprietary model. These are
# OUR invented formulas. The whole point of the wrapper is that this sheet never
# leaves the server.
# ----------------------------------------------------------------------------
ws_calc = wb.create_sheet("Calculations")
ws_calc["A1"] = "INTERNAL MODEL, NEVER EXPOSED TO THE CLIENT"
ws_calc["A1"].font = Font(bold=True, color="FFFFFF")
ws_calc["A1"].fill = PatternFill("solid", fgColor="7F1D1D")

calcs = [
    ("Conversion share",   "=in_line_conversion/100"),
    ("Biochar share",      "=in_biochar_rate/100"),
    ("Baseline carbon",    "=6.4"),
    ("Converted output",   "=in_plant_capacity*B2"),
    ("Feedstock tonnes",   "=in_plant_capacity*B2*B3*0.00065*(1/in_feedstock_yield)"),
    ("Opex feedstock",     "=B6*in_feedstock_cost"),
    ("Opex fixed",         "=165000*(in_plant_capacity/5000000)"),
    ("Gas savings value",  "=(in_plant_capacity*in_gas_consumption*B2*0.45/1000)*38"),
    ("Carbon revenue",     "=(in_plant_capacity*B2*B3*0.0091*in_feedstock_carbon)*in_carbon_price*in_credit_multiplier"),
]
for i, (label, formula) in enumerate(calcs, start=2):
    ws_calc[f"A{i}"] = label
    ws_calc[f"B{i}"] = formula
ws_calc.column_dimensions["A"].width = 24

# ----------------------------------------------------------------------------
# SHEET 3: Outputs. The only values the wrapper ever reads and returns.
# ----------------------------------------------------------------------------
ws_out = wb.create_sheet("Outputs")
ws_out["A1"] = "OUTPUT"
ws_out["B1"] = "VALUE"
ws_out["C1"] = "UNIT"
for c in ("A1", "B1", "C1"):
    ws_out[c].font = Font(bold=True)

outputs = [
    ("Gas displacement pct",  "=MIN(100,Calculations!B2*62)",                                   "percent",       "out_gas_pct"),
    ("Gas displacement MWh",  "=in_plant_capacity*in_gas_consumption*Calculations!B2*0.45/1000", "MWh/yr",        "out_gas_mwh"),
    ("Gypsum saved pct",      "=MIN(100,Calculations!B3*145)",                                  "percent",       "out_gypsum_pct"),
    ("Gypsum saved tonnes",   "=in_plant_capacity*Calculations!B2*Calculations!B3*0.052*in_feedstock_yield", "tonnes/yr", "out_gypsum_tonnes"),
    ("Net embodied carbon",   "=Calculations!B4-(Calculations!B2*Calculations!B3*22*in_feedstock_carbon)", "kgCO2e/m2", "out_net_carbon"),
    ("Annual CO2 removed",    "=in_plant_capacity*Calculations!B2*Calculations!B3*0.0091*in_feedstock_carbon", "tonnes/yr", "out_cdr_tonnes"),
    ("Capex",                 "=2600000*(in_plant_capacity/5000000)*(0.6+Calculations!B2*0.4)", "GBP",           "out_capex"),
    ("Opex",                  "=Calculations!B7+Calculations!B8",                               "GBP/yr",        "out_opex"),
    ("Unit cost",             "=IF(Calculations!B5>0,(Calculations!B7+Calculations!B8)/Calculations!B5,0)", "GBP/m2", "out_unit_cost"),
    ("Net annual cash flow",  "=Calculations!B9+Calculations!B10-(Calculations!B7+Calculations!B8)", "GBP/yr",   "out_net_cash"),
    ("Payback years",         "=IF(out_net_cash>0,out_capex/out_net_cash,-1)",                   "years",         "out_payback"),
    ("NPV 10yr at 8pct",      "=-out_capex+out_net_cash*((1-(1.08^-10))/0.08)",                 "GBP",           "out_npv"),
]
for i, (label, formula, unit, name) in enumerate(outputs, start=2):
    ws_out[f"A{i}"] = label
    ws_out[f"B{i}"] = formula
    ws_out[f"C{i}"] = unit
    ref = f"{quote_sheetname(ws_out.title)}!{absolute_coordinate(f'B{i}')}"
    wb.defined_names.add(DefinedName(name, attr_text=ref))

ws_out.column_dimensions["A"].width = 24
ws_out.column_dimensions["C"].width = 14

# Internal-only outputs, exposed to Adaptavate Mode but never to a partner.
ws_int = wb.create_sheet("Internal")
ws_int["A1"] = "INTERNAL OUTPUT"; ws_int["B1"] = "VALUE"
internals = [
    ("Feedstock tonnes",  "=Calculations!B6", "int_feedstock_tonnes"),
    ("Converted output",  "=Calculations!B5", "int_converted_output"),
    ("Gas savings value", "=Calculations!B9", "int_gas_savings"),
    ("Carbon revenue",    "=Calculations!B10", "int_carbon_revenue"),
]
for i, (label, formula, name) in enumerate(internals, start=2):
    ws_int[f"A{i}"] = label
    ws_int[f"B{i}"] = formula
    ref = f"{quote_sheetname(ws_int.title)}!{absolute_coordinate(f'B{i}')}"
    wb.defined_names.add(DefinedName(name, attr_text=ref))
ws_int.column_dimensions["A"].width = 22


out = pathlib.Path(__file__).resolve().parent.parent / "model" / "Adaptavate-BBE-TEST-model.xlsx"
out.parent.mkdir(parents=True, exist_ok=True)
wb.save(out)
print(f"Workbook written to {out}")
print("Named ranges defined:", len(wb.defined_names))
for n in wb.defined_names:
    print("  ", n, "->", wb.defined_names[n].attr_text)
