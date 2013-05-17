import datetime
from bihar.calculations.types import DoneDueCalculator, TotalCalculator
from bihar.calculations.utils.calculations import get_forms
from bihar.calculations.utils.filters import is_pregnant_mother,\
    get_add, get_edd, A_MONTH
from bihar.calculations.utils.home_visit import GRACE_PERIOD
from bihar.calculations.utils.visits import visit_is, has_visit
import fluff


class BPCalculator(DoneDueCalculator):

    def __init__(self, days, n_visits, window=A_MONTH):
        self.days = days
        self.n_visits = n_visits
        super(BPCalculator, self).__init__(window)

    def filter(self, case):
        return is_pregnant_mother(case) and get_edd(case)

    @fluff.date_emitter
    def numerator(self, case):
        yield case.edd - datetime.timedelta(days=self.days) + GRACE_PERIOD

    @fluff.null_emitter
    def total(self, case):
        n_visits = len(filter(lambda a: visit_is(a, 'bp'), case.actions))
        if n_visits >= self.n_visits:
            yield None


class VisitCalculator(DoneDueCalculator):

    def __init__(self, schedule, visit_type, window=A_MONTH):
        self.schedule = schedule
        self.visit_type = visit_type
        super(VisitCalculator, self).__init__(window)

    def filter(self, case):
        return is_pregnant_mother(case) and get_add(case)

    @fluff.date_emitter
    def numerator(self, case):
        n_qualifying_visits = len(
            filter(lambda a: visit_is(a, self.visit_type), case.actions)
        )
        # What's below is true to the original, but I think it should be
        # self.schedule[:n_qualifying_visits]
        # to be revisited
        if n_qualifying_visits != 0:
            for days in self.schedule[:n_qualifying_visits - 1]:
                yield case.add + datetime.timedelta(days=days) + GRACE_PERIOD

    @fluff.date_emitter
    def total(self, case):
        for days in self.schedule:
            yield case.add + datetime.timedelta(days=days) + GRACE_PERIOD


class DueNextMonth(TotalCalculator):
    """Abstract"""

    window = 2 * A_MONTH

    @fluff.filter_by
    def has_edd(self, case):
        return get_edd(case)

    @fluff.date_emitter
    def total(self, case):
        yield get_edd(case) - self.window / 2


class UpcomingDeliveryList(DueNextMonth):

    def filter(self, case):
        return is_pregnant_mother(case) and not get_add(case)


class RecentDeliveryList(TotalCalculator):

    window = A_MONTH

    def filter(self, case):
        return is_pregnant_mother(case) and get_add(case)

    @fluff.date_emitter
    def total(self, case):
        yield get_add(case)


class RecentlyOpened(TotalCalculator):
    """Abstract"""

    window = A_MONTH

    @fluff.date_emitter
    def total(self, case):
        yield case.opened_on


class RecentRegistrationList(RecentlyOpened):

    def filter(self, case):
        return is_pregnant_mother(case)


class NoBPList(RecentlyOpened):

    def filter(self, case):
        return is_pregnant_mother(case) and not has_visit(case, 'bp')


class NoIFAList(RecentlyOpened):

    def filter(self, case):
        ifa = int(getattr(case, "ifa_tablets", None) or 0)
        return is_pregnant_mother(case) and ifa > 0


class NoBPPrep(TotalCalculator):
    """Abstract"""
    no_prep_rules = ()

    def action_filter(self, action):
        return visit_is(action, 'bp')

    @fluff.filter_by
    def no_prep(self, case):
        return any((
            all((
                form.xpath(xpath) == value
                for xpath, value in self.no_prep_rules
            ))
            for form in get_forms(case, action_filter=self.action_filter)
        ))


class NoEmergencyPrep(NoBPPrep, DueNextMonth):

    no_prep_rules = (
        ('form/bp2/maternal_danger_signs', 'no'),
        ('form/bp2/danger_institution', 'no'),
    )

    def filter(self, case):
        return is_pregnant_mother(case) and not get_add(case)


class NoNewbornPrep(NoBPPrep, DueNextMonth):

    no_prep_rules = (
        ('form/bp2/wrapping', 'no'),
        ('form/bp2/skin_To_skin', 'no'),
        ('form/bp2/immediate_breastfeeding', 'no'),
        ('form/bp2/cord_care', 'no'),
    )


class NoPostpartumCounseling(NoBPPrep, DueNextMonth):

    no_prep_rules = (
        ('form/bp2/counsel_accessible', 'no'),
    )


class NoFamilyPlanning(DueNextMonth):
    def filter(self, case):
        return getattr(case, 'couple_interested', None) == 'no'
