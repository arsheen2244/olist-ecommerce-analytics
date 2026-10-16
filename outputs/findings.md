# Findings: Olist e-commerce analysis

## Headline numbers
- **98,199** valid orders from **94,983** unique customers, 2016-09 to 2018-09
- GMV **R$13,494,401**, average order value **R$137**
- **6.8%** of delivered orders arrived late; average review **4.12/5**

## What the data says
1. **Revenue is concentrated.** 18 of 74 categories generate 80% of revenue; the top three are health beauty, watches gifts, bed bath table.
2. **Late delivery is associated with much lower satisfaction.** On-time orders average 4.29 stars vs 2.27 for late orders (gap 2.02, 95% CI [1.98, 2.06]). In the worst bucket (8+ days late), 79% of reviews are 1-2 stars vs 9% for on-time orders.
3. **Delivery problems are geographic.** AL has the highest late rate (21.4% vs 6.8% overall); on average orders there arrive 8.7 days earlier than promised, so the problem is the late tail, not the average.
4. **Customers rarely come back, and a good first review does not change that.** Only 3.0% of customers ordered more than once. Repeat rates are 2.8% after a 1-2 star first order vs 3.0% after 4-5 stars (difference 0.2 pts, 95% CI [-0.1, 0.5], which includes zero), so first-order satisfaction does not explain who returns. Low retention looks structural, not a service-quality problem.
5. **RFM segmentation.** The 'Lapsed big spenders' segment is 22.1% of customers but 41.9% of revenue (average spend R$269).
6. **A short list of sellers carries a lot of risk.** Of 804 sellers with 20+ delivered orders, 27 are in the top revenue quartile with poor reviews or frequent late deliveries; they account for 7% of scored seller revenue.
7. **Payments.** Credit cards are 78% of payment value with 3.5 instalments on average.
8. **Shipping is a bigger burden far from the hub.** Freight is 28% of item value in RR vs 17% across all orders.

## Recommendations (with illustrative sizing)
1. **Fix the delivery promise in the five worst states** (AL, MA, SE, PI, CE): bringing them to the national late rate would remove about **286** late deliveries over the period, via better carriers or more realistic estimates.
2. **Run a seller-performance programme** starting with the 27 flagged sellers (see `outputs/08_seller_scorecard.csv`): delivery SLAs, coaching, or reduced search ranking until they improve.
3. **Treat retention as its own problem.** Only 3.0% of customers return, and review scores do not predict who does, so fixing service alone will not move repeat rate. Test a second-purchase incentive (voucher or reminder) on a random half of new customers and compare repeat rates; this is an A/B test, not something this data can size.

## Caveats
- These are associations, not proven causes: unhappy customers may differ in ways the data does not capture.
- Review scores exist only for customers who responded; non-response bias is possible.
- Customer identity is `customer_unique_id`; one person using different accounts would look like two customers.
- Revenue excludes freight and cancelled/unavailable orders; retention windows near the end of the data are incomplete.

## Resume bullet (check every number against outputs/ before using)
> Analysed 98,199 marketplace orders (R$13,494,401 GMV) with SQL (CTEs, window functions, cohort and RFM analysis) and Python; showed late deliveries cut average review scores from 4.3 to 2.3 and that only 3.0% of customers ever reorder regardless of first-order satisfaction; shipped a Streamlit dashboard and a prioritised fix list for 27 high-risk sellers.
