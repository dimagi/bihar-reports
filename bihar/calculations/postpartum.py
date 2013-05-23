import datetime
from couchdbkit import ResourceNotFound
from bihar.calculations.utils.calculations import get_forms
from bihar.calculations.utils.xmlns import DELIVERY, PNC, EBF, REGISTRATION
from dimagi.utils.parsing import string_to_datetime
from bihar.calculations.types import DoneDueCalculator, TotalCalculator
from bihar.calculations.utils.filters import get_add, A_MONTH
import fluff


class Complications(DoneDueCalculator):
    """
        DENOM: [
            any DELIVERY forms with (
                complications = 'yes'
            ) in last 30 days
            PLUS any PNC forms with ( # 'any applicable from PNC forms with' (?)
                abdominal_pain ='yes' or
                bleeding = 'yes' or
                discharge = 'yes' or
                fever = 'yes' or
                pain_urination = 'yes'
            ) in the last 30 days
            PLUS any REGISTRATION forms with (
                abd_pain ='yes' or    # == abdominal_pain
                fever = 'yes' or
                pain_urine = 'yes' or    # == pain_urination
                vaginal_discharge = 'yes'    # == discharge
            ) with add in last 30 days
            PLUS any EBF forms with (
                abdominal_pain ='yes' or
                bleeding = 'yes' or
                discharge = 'yes' or
                fever = 'yes' or
                pain_urination = 'yes'
            ) in last 30 days    # note, don't exist in EBF yet, but will shortly
        ]
        NUM: [
            filter (
                DELIVERY ? form.meta.timeStart - child_info/case/update/time_of_birth,
                REGISTRATION|PNC|EBF ? form.meta.timeStart - case.add
            ) < `days` days
        ]
    """
    window = A_MONTH

    def case_open(self, case):
        """Include all cases"""
        return True

    _pnc_ebc_complications = (
        'abdominal_pain',
        'bleeding',
        'discharge',
        'fever',
        'pain_urination',
    )
    _reg_del_complications = (
        'abd_pain',
        'fever',
        'pain_urine',
        'vaginal_discharge',
    )
    complications_by_form = {
        REGISTRATION: _reg_del_complications,
        DELIVERY: _reg_del_complications,
        PNC: _pnc_ebc_complications,
        EBF: _pnc_ebc_complications,
    }

    def __init__(self, days, window=None):
        super(Complications, self).__init__(window=window)
        self.days = datetime.timedelta(days=days)

    @fluff.date_emitter
    def numerator(self, case):
        date = self._calculate_both(case)[0]
        if date:
            yield date

    @fluff.date_emitter
    def total(self, case):
        date = self._calculate_both(case)[1]
        if date:
            yield date

    def get_forms_with_complications(self, case):
        for form, action in get_forms(case, yield_action=True):
            try:
                complication_paths = self.complications_by_form[form.xmlns]
            except KeyError:
                continue
            else:
                for p in complication_paths:
                    if form.xpath('form/' + p) == 'yes':
                        yield form, action.date

    def _calculate_both(self, case):
        complication_date = None
        complication_shortly_after_birth_date = None
        if case.type == 'cc_bihar_pregnancy':
            for form, date in self.get_forms_with_complications(case):
                complication_date = date
                if form.xmlns == DELIVERY:
                    add = form.xpath('form/add')
                else:
                    add = get_add(case)
                add = string_to_datetime(add).date()
                if form.metadata.timeStart.date() - add <= self.days:
                    complication_shortly_after_birth_date = date

        return complication_shortly_after_birth_date, complication_date