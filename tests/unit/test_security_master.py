import pytest
from datetime import date
from equity_engine.security_master.master import SecurityMaster

def test_security_master_lifecycle(tmp_path):
    db_file = tmp_path / "sm.db"
    sm = SecurityMaster(str(db_file))
    
    # 1. Add instrument
    start_date = date(2020, 1, 1)
    inst_id = sm.add_instrument(
        isin="INE123456789",
        nse_symbol="OLDNAME",
        company_name="Old Name Ltd",
        valid_from=start_date
    )
    
    # 2. Get by symbol
    inst1 = sm.get_instrument_by_symbol("OLDNAME", date(2021, 1, 1))
    assert inst1 is not None
    assert inst1["instrument_id"] == inst_id
    
    # 3. Handle symbol change
    change_date = date(2022, 1, 1)
    sm.handle_symbol_change(
        instrument_id=inst_id,
        new_nse_symbol="NEWNAME",
        new_company_name="New Name Ltd",
        change_date=change_date
    )
    
    # 4. Check old date
    inst_old = sm.get_instrument_by_symbol("OLDNAME", date(2021, 12, 31))
    assert inst_old is not None
    assert inst_old["company_name"] == "Old Name Ltd"
    
    inst_old_new = sm.get_instrument_by_symbol("NEWNAME", date(2021, 12, 31))
    assert inst_old_new is None
    
    # 5. Check new date
    inst_new = sm.get_instrument_by_symbol("NEWNAME", date(2022, 1, 2))
    assert inst_new is not None
    assert inst_new["company_name"] == "New Name Ltd"
    assert inst_new["instrument_id"] == inst_id
    
    inst_new_old = sm.get_instrument_by_symbol("OLDNAME", date(2022, 1, 2))
    assert inst_new_old is None

    # 6. Check all instruments
    all_inst = sm.get_all_instruments(date(2022, 1, 2))
    assert len(all_inst) == 1
    assert all_inst["nse_symbol"][0] == "NEWNAME"
