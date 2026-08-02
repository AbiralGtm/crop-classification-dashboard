"""Hardcoded reference statistics for sanity-checking model output against
real published numbers.

Source: Nepal's Ministry of Agriculture and Livestock Development (MoALD),
"Statistical Information on Nepalese Agriculture", 2079/80 (FY 2022/23) --
major cereal crops (paddy, maize, wheat, millet, barley, buckwheat) combined,
Rupandehi district total.
https://giwmscdnone.gov.np/media/pdf_upload/MOALD-Statical-Book-Magre-2081-Final_wgfs8ph.pdf

This is a DISTRICT-WIDE total across all of Rupandehi (a large area, roughly
60,000-70,000 ha of agricultural land overall) and combines six different
crops -- it is not a per-crop-type breakdown. It's only precise enough for a
rough order-of-magnitude sanity check ("is my AOI's predicted cropped area a
plausible fraction of the whole district's cropland, or is it larger than
the entire district, which would be an obvious red flag"), not a real
validation of per-crop accuracy. A per-crop, per-season breakdown would need
to be pulled from the same source's detailed tables, which were not
extracted here -- treat this as a starting point, not a finished dataset.
"""

RUPANDEHI_DISTRICT_NAME = "Rupandehi"
RUPANDEHI_MAJOR_CEREAL_AREA_HA = 92_967
RUPANDEHI_MAJOR_CEREAL_PRODUCTION_MT = 369_089
RUPANDEHI_MAJOR_CEREAL_YIELD_MT_PER_HA = 3.97
RUPANDEHI_FISCAL_YEAR = "2079/80 (2022/23)"
RUPANDEHI_SOURCE = (
    "MoALD, Statistical Information on Nepalese Agriculture, 2079/80 (2022/23) -- "
    "paddy, maize, wheat, millet, barley, and buckwheat combined"
)
