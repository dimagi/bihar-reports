import datetime
from django.utils.translation import ugettext_noop as _
from bihar.calculations.pregnancy import BirthPlace
from bihar.calculations.types import TotalCalculator, DoneDueCalculator, AddCalculator
from bihar.calculations.utils.calculations import _get_actions
from bihar.calculations.utils.filters import is_pregnant_mother, A_MONTH, is_newborn_child
from bihar.calculations.utils.xmlns import DELIVERY
import fluff


def latest_action_date(actions):
    dates = [action.date for action in actions]
    if dates:
        return max(dates)
    else:
        return None


def is_stillborn(case):
    properties = (
        'child_cried',
        'child_breathing',
        'child_movement',
        'child_heartbeats'
    )
    for action in _get_actions(case, action_filter=lambda a: a.xform_xmlns == DELIVERY):
        xform = action.xform
        print xform.get_id
        if xform.form.get('has_delivered') != 'yes':
            continue
        for p in properties:
            value = xform.xpath('form/child_info/%s' % p)
            if not value:
                child_infos = xform.xpath('form/child_info')
                for child_info in child_infos:
                    child_info.get(p)
                    print '(nested) %s: %s' % (p, value)
                    if value != 'no':
                        return False
            else:
                print '%s: %s' % (p, value)
                if value != 'no':
                    return False
    return True

class MMCalculator(TotalCalculator):
    """
    [DELIVERY form] filter by mother_alive = 'no' and where date_death - form_case_update_add <= 42
    OR [PNC form] filter by form_mother_child_alive = 'no' which is 0 for this variable' and date_death - form_form_case_update_add <= 42
    """
    _('Maternal mortality')

    window = A_MONTH

    def filter(self, case):
        return is_pregnant_mother(case)

    @fluff.date_emitter
    def total(self, case):

        def mother_died(a):
            # todo: incomplete
            return (
                a.updated_known_properties.get('mother_alive') == 'no'
                and a.xform_xmlns == DELIVERY
            )

        date = latest_action_date(_get_actions(case, action_filter=mother_died))

        if date:
            yield date


class IMCalculator(TotalCalculator):
    """
    (
        [DELIVERY form] child_alive = 'no' and  chld_date_death - form_case_update_add
        OR [PNC form] child_alive = 'no' and chld_date_death - form_case_update_add
    ) <= 365
    """
    _('Infant mortality')

    window = datetime.timedelta(days=365)

    def filter(self, case):
        return is_newborn_child(case)

    @fluff.date_emitter
    def total(self, case):
        def child_died(a):
            return a.updated_known_properties.get('child_alive', None) == "no"

        date = latest_action_date(_get_actions(case, action_filter=child_died))
        if date:
            yield date


class StillBirth(TotalCalculator, AddCalculator):

    window = A_MONTH

    @fluff.filter_by
    def is_stillborn(self, case):
        return is_stillborn(case)


class StillBirthPlace(StillBirth, BirthPlace):
    _('Still Births at Government Hospital')
    _('Still Births at Home')

    window = A_MONTH


class LiveBirth(TotalCalculator, AddCalculator):
    _('Live Births')

    window = A_MONTH

    @fluff.filter_by
    def not_stillborn(self, case):
        return not is_stillborn(case)
