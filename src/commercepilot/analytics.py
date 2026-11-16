"""Deterministic variance and evaluated statistical baselines over recorded data."""
from datetime import date, timedelta
from fractions import Fraction
from pydantic import Field, model_validator
from commercepilot.business import Business
from commercepilot.domain import Command


class ForecastInput(Command):
    ends_on: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    history_days: int = Field(default=28, ge=28, le=180)
    horizon_days: int = Field(default=7, ge=1, le=30)


def mean(values):
    return Fraction(sum(values), len(values))


def predict(values, horizon, method):
    if method == "weekly_naive":
        return [Fraction(values[-7 + i % 7]) for i in range(horizon)]
    return [mean(values)] * horizon


def rounded(value):
    return round(value)  # Fraction rounds without binary floating-point loss.


class Analytics:
    def __init__(self, services):
        self.business = Business(services)

    def period(self, merchant, starts_on, ends_on, currency):
        if (ends_on-starts_on).days not in range(366):
            raise ValueError("report periods must contain 1 to 366 days")
        days = [self.business.daily(merchant, starts_on+timedelta(days=i),currency) for i in range((ends_on-starts_on).days+1)]
        fields = ["net_sales_minor", "sales_after_refunds_minor", "cash_after_refunds_minor", "gross_profit_minor", "operating_profit_minor", "expenses_minor"]
        totals = {field: sum(d[field] for d in days) if all(d[field] is not None for d in days) else None for field in fields}
        return {"starts_on":starts_on.isoformat(),"ends_on":ends_on.isoformat(),"currency":currency,"totals":totals,"incomplete_days":[d["day"] for d in days if d["missing"]],"source_ids":sorted({source for d in days for source in d["source_ids"]}),"coverage":"recorded_data_only"}

    def variance(self, merchant, plan_id):
        plan = self.business.plan(merchant, plan_id)
        p = plan["plan"]
        actual = self.period(merchant,date.fromisoformat(p["starts_on"]),date.fromisoformat(p["ends_on"]),p["currency"])
        revenue, expenses = actual["totals"]["net_sales_minor"], actual["totals"]["expenses_minor"]
        return {"plan_id":plan_id,"plan_state":plan["state"],"payload_hash":plan["payload_hash"],"actual":actual,
                "revenue_variance_minor": None if revenue is None else revenue-p["revenue_target_minor"],
                "expense_variance_minor": None if expenses is None else expenses-p["expense_budget_minor"],
                "interpretation":"revenue positive means above target; expense positive means above budget; no spending committed"}

    def forecast(self, merchant, data):
        starts_on = data.ends_on-timedelta(days=data.history_days-1)
        days=[self.business.daily(merchant,starts_on+timedelta(days=i),data.currency) for i in range(data.history_days)]
        absent=[d["day"] for d in days if d["net_sales_minor"] is None]
        meta={"history_starts_on":starts_on.isoformat(),"history_ends_on":data.ends_on.isoformat(),"currency":data.currency,
              "horizon_days":data.horizon_days,"assumptions":["Latest recorded booked-order snapshots represent each historical day.","No unobserved sales, price changes, seasonality beyond a week or future shocks are modelled."],
              "limitations":["Recorded data is not independently reconciled.","Empirical error bands are scenarios, not calibrated confidence intervals.","No inventory or purchasing commitment is made."]}
        if absent:
            return {**meta,"state":"insufficient_history","missing_days":absent,"required":"At least 28 consecutive days with explicit order history; unobserved days cannot be treated as zero."}
        series=[d["net_sales_minor"] for d in days]
        training,holdout=series[:-7],series[-7:]
        scores={}
        for method in ["mean_baseline","weekly_naive"]:
            values=predict(training,7,method)
            absolute=sum(abs(y-p) for y,p in zip(holdout,values))
            denominator=sum(abs(y) for y in holdout)
            scores[method]={"mae_minor":rounded(absolute/7),"wape":float(absolute/denominator) if denominator else None}
        # Select by exact absolute error, avoiding rounded metric ties.
        method=min(scores,key=lambda m:sum(abs(y-p) for y,p in zip(holdout,predict(training,7,m))))
        errors=sorted(abs(y-p) for y,p in zip(holdout,predict(training,7,method)))
        band=errors[-1]  # Largest observed holdout error, deliberately descriptive.
        projection=predict(series,data.horizon_days,method)
        points=[{"day":(data.ends_on+timedelta(days=i+1)).isoformat(),"base_minor":rounded(value),"downside_minor":rounded(max(Fraction(0),value-band)),"optimistic_minor":rounded(value+band)} for i,value in enumerate(projection)]
        return {**meta,"state":"estimated","metric":"net_sales_minor","method":method,"method_version":"baseline-v1","backtest":{"holdout_days":7,"scores":scores},"daily":points,"source_ids":sorted({source for d in days for source in d["source_ids"]})}
