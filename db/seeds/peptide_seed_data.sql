-- =============================================================================
-- Seed: peptide_seed_data.sql
-- Description: Initial 12 rows for peptide_condition_library — covering AR,
--              ESR1, ESR2, OXTR, MC4R, GLP1R, RET, TP53, and BRCA1 gene-
--              variant-peptide combinations for the PeptidIQ V3 menopause/
--              HRT protocol response engine.
-- Author:  PeptidIQ Engineering
-- Date:    2026-04-08
-- Depends: 003_peptide_condition_library.sql
-- =============================================================================

BEGIN;

INSERT INTO peptide_condition_library (
    gene_symbol,
    variant_type,
    rsid,
    variant_description,
    peptide_name,
    peptide_class,
    target_receptor,
    response_direction,
    confidence_tier,
    mechanism_summary,
    dosing_guidance,
    trade_off_text,
    contraindication_flag,
    contraindication_genes,
    kegg_pathways,
    source_pmids
)
VALUES

-- -------------------------------------------------------------------------
-- Row 1: AR / Short CAG repeat / Testosterone (topical) — ENHANCED
-- -------------------------------------------------------------------------
(
    'AR',
    'STR_repeat',
    NULL,
    'CAG repeat < 22 (short)',
    'Testosterone (topical)',
    'Androgen',
    'AR',
    'enhanced',
    'B',
    'Short AR CAG repeat (< 22) produces a hypersensitive androgen receptor with increased transactivation efficiency. Lower testosterone concentrations achieve equivalent downstream gene activation. Inverse correlation between CAG length and receptor transcriptional activity is well-established.',
    'Start at lower quartile of standard range (e.g., 0.25 mg topical instead of 0.5 mg). Monitor for androgenic excess at 4 weeks: acne, hair thinning, mood changes. Monthly CBC for polycythemia.',
    'Testosterone converts to DHT via 5-alpha-reductase (SRD5A2). Short CAG + high SRD5A2 activity = amplified DHT effects: hair loss, acne, LUTS. Monitor DHT:T ratio. Also converts to E2 via aromatase (CYP19A1) — monitor estradiol if symptoms of estrogen excess appear.',
    FALSE,
    NULL,
    ARRAY['map00140', 'hsa04912'],
    ARRAY['24165020', '23844628', '26421011']
),

-- -------------------------------------------------------------------------
-- Row 2: AR / Long CAG repeat / Testosterone (topical) — BLUNTED
-- -------------------------------------------------------------------------
(
    'AR',
    'STR_repeat',
    NULL,
    'CAG repeat > 27 (long)',
    'Testosterone (topical)',
    'Androgen',
    'AR',
    'blunted',
    'B',
    'Long AR CAG repeat (> 27) structurally perturbs the transactivation domain, requiring higher testosterone concentrations to achieve standard receptor activation. Patients may report subtherapeutic effects at standard doses.',
    'Start at standard dose but prepare for dose escalation at week 6 review. Consider pellet therapy for sustained higher levels if topical is insufficient. 3-month evaluation window before declaring treatment failure.',
    'Higher doses increase aromatization to estradiol. Monitor E2 at each dose escalation. Risk of polycythemia increases with supraphysiologic T levels.',
    FALSE,
    NULL,
    ARRAY['map00140', 'hsa04912'],
    ARRAY['24165020', '24593124', '21712734']
),

-- -------------------------------------------------------------------------
-- Row 3: AR / Pathologic CAG repeat > 35 / Testosterone (topical) — CONTRAINDICATED
-- -------------------------------------------------------------------------
(
    'AR',
    'STR_repeat',
    NULL,
    'CAG repeat > 35 (pathologic)',
    'Testosterone (topical)',
    'Androgen',
    'AR',
    'contraindicated',
    'A',
    'CAG repeat > 35 is in the Kennedy disease (SBMA) range. The expanded polyglutamine tract causes toxic protein aggregation in motor neurons. High-dose androgen therapy may accelerate neurotoxic aggregation.',
    'HALT androgen-based protocols. Mandatory neurology referral. This is a critical safety flag.',
    'Androgen receptor with > 35 CAG repeats is non-functional for therapeutic purposes and the expanded protein is directly neurotoxic under androgen stimulation.',
    TRUE,
    ARRAY['AR'],
    ARRAY['map00140'],
    ARRAY['24593124']
),

-- -------------------------------------------------------------------------
-- Row 4: ESR1 / rs2234693 PvuII T allele / Estradiol (E2) — ENHANCED
-- -------------------------------------------------------------------------
(
    'ESR1',
    'SNP',
    'rs2234693',
    'PvuII T allele',
    'Estradiol (E2)',
    'HRT',
    'ERalpha',
    'enhanced',
    'B',
    'ESR1 PvuII T allele is associated with enhanced non-genomic estrogen signaling via PI3K/AKT pathway and increased HDL response to estrogen therapy. Also associated with elevated breast cancer risk in multiple cohort studies.',
    'Standard estradiol dosing appropriate — patient may see above-average cardiovascular benefit. However, baseline mammography and annual breast monitoring recommended given elevated oncological risk.',
    'Enhanced estrogen signaling is a double-edged sword: cardioprotective (HDL, vascular function) but potentially oncogenic (ERalpha-driven breast proliferation). BRCA1/2 status must be confirmed before initiating estradiol in TT carriers.',
    FALSE,
    NULL,
    ARRAY['hsa04915', 'hsa04151'],
    ARRAY['17713466', '20827267', '17889406']
),

-- -------------------------------------------------------------------------
-- Row 5: ESR2 / rs1256049 A allele / Estradiol (E2) — ENHANCED (VTE flag)
-- -------------------------------------------------------------------------
(
    'ESR2',
    'SNP',
    'rs1256049',
    'A allele',
    'Estradiol (E2)',
    'HRT',
    'ERbeta',
    'enhanced',
    'B',
    'ESR2 rs1256049 A allele is associated with increased deep vein thrombosis and venous thromboembolism risk in HRT users. ERbeta modulates coagulation factor expression.',
    'This is a safety flag, not a dosing adjustment. Screen for VTE risk factors before initiating estrogen therapy. Consider transdermal route (lower VTE risk than oral). Avoid oral estrogen in carriers with additional VTE risk factors (Factor V Leiden, obesity, immobility).',
    'VTE risk is the primary trade-off. Oral estrogen increases hepatic clotting factor synthesis; transdermal bypasses first-pass metabolism and substantially reduces VTE risk. Genotype-informed route selection is the actionable recommendation.',
    FALSE,
    NULL,
    ARRAY['hsa04915'],
    ARRAY['17184825']
),

-- -------------------------------------------------------------------------
-- Row 6: OXTR / rs53576 AA genotype / Oxytocin (intranasal) — ENHANCED
-- -------------------------------------------------------------------------
(
    'OXTR',
    'SNP',
    'rs53576',
    'AA genotype',
    'Oxytocin (intranasal)',
    'Neuropeptide',
    'OXTR',
    'enhanced',
    'C',
    'OXTR rs53576 AA carriers have reduced baseline oxytocin receptor sensitivity and lower prosocial affect. Paradoxically, these patients may benefit most from exogenous oxytocin supplementation because they have the most room for improvement. Combined with ESR1 PvuII T allele, AA carriers showed significantly enhanced arousal and orgasm scores (FSFI).',
    'Standard intranasal oxytocin protocol. Consider co-administration with PT-141 for HSDD-presenting patients, especially if ESR1 PvuII T allele also present.',
    'Estrogen primes OXTR expression — declining estrogen in menopause reduces OXTR density. Exogenous oxytocin without estrogen co-administration may have reduced efficacy. Consider estradiol status when prescribing.',
    FALSE,
    NULL,
    ARRAY['hsa04726'],
    ARRAY['28093060', '26150031']
),

-- -------------------------------------------------------------------------
-- Row 7: MC4R / Loss-of-function variants / PT-141 (Bremelanotide) — BLUNTED
-- -------------------------------------------------------------------------
(
    'MC4R',
    'SNP',
    NULL,
    'Loss-of-function variants',
    'PT-141 (Bremelanotide)',
    'Melanocortin Agonist',
    'MC3R/MC4R',
    'blunted',
    'B',
    'MC4R loss-of-function variants reduce downstream melanocortin signaling. PT-141 (bremelanotide) is an MC3R/MC4R agonist. Reduced receptor function blunts the hypothalamic arousal cascade that PT-141 depends on.',
    'PT-141 may be ineffective. Consider alternative approaches for HSDD: oxytocin (different pathway), kisspeptin (upstream HPG axis), or combined oxytocin + low-dose PT-141.',
    'MC4R LOF is also associated with severe obesity and hyperphagia. If MC4R LOF is detected, the weight management conversation is as important as the sexual function conversation.',
    FALSE,
    NULL,
    ARRAY['hsa04916'],
    ARRAY['32487249', '23512951']
),

-- -------------------------------------------------------------------------
-- Row 8: GLP1R / rs3765467 A allele (Lys168Arg) / Semaglutide — BLUNTED
-- -------------------------------------------------------------------------
(
    'GLP1R',
    'SNP',
    'rs3765467',
    'A allele (Lys168Arg)',
    'Semaglutide',
    'GLP-1 RA',
    'GLP1R',
    'blunted',
    'B',
    'GLP1R rs3765467 (Lys168Arg) reduces GLP-1 binding affinity at the receptor. Lower binding affinity means standard semaglutide doses may produce subtherapeutic incretin signaling.',
    'Start at standard dose but set expectation for dose escalation at week 4. If < 5% body weight loss at 8 weeks on maximum tolerated dose, the genetic basis for reduced response is documented — switch to tirzepatide (dual GLP1R/GIPR agonist) which may partially compensate via the GIP pathway.',
    'Higher semaglutide doses increase GI side effects (nausea, vomiting, diarrhea). Dose escalation should be slow (every 4 weeks). Also screen RET proto-oncogene — GLP-1 RAs are contraindicated in MEN2/medullary thyroid carcinoma family history.',
    FALSE,
    NULL,
    ARRAY['hsa04151', 'hsa04920'],
    ARRAY['34170647']
),

-- -------------------------------------------------------------------------
-- Row 9: GLP1R / rs6923761 A allele (Arg131Gln) / Tirzepatide — BLUNTED
-- -------------------------------------------------------------------------
(
    'GLP1R',
    'SNP',
    'rs6923761',
    'A allele (Arg131Gln)',
    'Tirzepatide',
    'GLP-1 RA',
    'GLP1R/GIPR',
    'blunted',
    'B',
    'GLP1R rs6923761 (Arg131Gln) blunts GLP-1-stimulated insulin secretion. Tirzepatide''s dual GLP1R/GIPR agonism may partially compensate via the GIP pathway, but baseline GLP-1 sensitivity is reduced.',
    'Tirzepatide may outperform semaglutide in this genotype due to dual receptor engagement. Start at standard dose. Note: postmenopausal women on tirzepatide + MHT showed 35% greater weight loss than tirzepatide alone — estrogen status modifies GLP-1 RA efficacy.',
    'Same GI side effect profile as semaglutide. Additionally, rapid weight loss (> 1 kg/week) increases gallstone risk. Monitor hepatobiliary symptoms. PCSK9 LOF carriers may have altered bile acid metabolism — additional monitoring warranted.',
    FALSE,
    NULL,
    ARRAY['hsa04151', 'hsa04920'],
    ARRAY['34170647']
),

-- -------------------------------------------------------------------------
-- Row 10: RET / Pathogenic (MEN2) / Semaglutide — CONTRAINDICATED
-- -------------------------------------------------------------------------
(
    'RET',
    'SNP',
    NULL,
    'Pathogenic (MEN2)',
    'Semaglutide',
    'GLP-1 RA',
    'GLP1R',
    'contraindicated',
    'A',
    'RET proto-oncogene pathogenic variants cause Multiple Endocrine Neoplasia type 2 (MEN2) including medullary thyroid carcinoma (MTC). GLP-1 RAs caused thyroid C-cell tumors in rodent studies. FDA black box warning on all GLP-1 RAs.',
    'ABSOLUTE CONTRAINDICATION. Do not prescribe any GLP-1 RA (semaglutide, tirzepatide, liraglutide) in patients with RET pathogenic variants or personal/family history of MTC or MEN2.',
    'N/A — this is a hard contraindication, not a trade-off.',
    TRUE,
    ARRAY['RET'],
    ARRAY[]::TEXT[],
    ARRAY[]::TEXT[]
),

-- -------------------------------------------------------------------------
-- Row 11: TP53 / Pathogenic variants / BPC-157 — CONTRAINDICATED
-- -------------------------------------------------------------------------
(
    'TP53',
    'SNP',
    NULL,
    'Pathogenic variants',
    'BPC-157',
    'Tissue Repair',
    'VEGFR/EGFR/FAK',
    'contraindicated',
    'C',
    'BPC-157 promotes angiogenesis via VEGFR pathway and tissue growth via EGFR/FAK signaling. In a patient with TP53 pathogenic variants (Li-Fraumeni syndrome or somatic driver), these pro-growth signals may promote tumor vascularization and proliferation.',
    'CONTRAINDICATED. Do not prescribe BPC-157 in patients with TP53 pathogenic variants. Screen APC and KRAS as well — any active oncogenic driver is a contraindication to pro-angiogenic peptides.',
    'N/A — hard contraindication in the presence of oncogenic driver mutations.',
    TRUE,
    ARRAY['TP53', 'APC', 'KRAS'],
    ARRAY[]::TEXT[],
    ARRAY[]::TEXT[]
),

-- -------------------------------------------------------------------------
-- Row 12: BRCA1 / Pathogenic variants / Kisspeptin-10/54 — CONTRAINDICATED
-- -------------------------------------------------------------------------
(
    'BRCA1',
    'SNP',
    NULL,
    'Pathogenic variants',
    'Kisspeptin-10/54',
    'Neuropeptide',
    'KISS1R',
    'contraindicated',
    'B',
    'Kisspeptin activates KISS1R on GnRH neurons, stimulating LH/FSH secretion, which in turn stimulates ovarian estrogen production. In BRCA1/2 pathogenic carriers, stimulating estrogen synthesis increases breast and ovarian cancer risk.',
    'CONTRAINDICATED in BRCA1/2 pathogenic carriers unless oophorectomy has been performed (removing the estrogen source). If ovaries are intact, use non-estrogenic approaches for hot flash management.',
    'Kisspeptin''s mechanism of action inherently stimulates the HPG axis and estrogen production. This is the desired effect for most menopause patients but is the exact wrong signal in hereditary breast/ovarian cancer syndrome.',
    TRUE,
    ARRAY['BRCA1', 'BRCA2'],
    ARRAY['hsa04912'],
    ARRAY[]::TEXT[]
),

-- =========================================================================
-- V3 EXPANSION — 18 ADDITIONAL ROWS (Rows 13-30)
-- Covers: GLP1R, FSHR, CYP19A1, COMT, PGR, OXTR, MC4R, GPER1, HTR1A
-- =========================================================================

-- Row 13: GLP1R / rs6923761 / GLP-1 Agonist — ENHANCED
(
    'GLP1R',
    'SNP',
    'rs6923761',
    'GLP1R sensitivity variant (Ala316Thr)',
    'Semaglutide',
    'GLP-1 Agonist',
    'GLP1R',
    'enhanced',
    'A',
    'rs6923761 increases GLP-1 receptor ligand affinity, producing enhanced incretin signaling at standard doses. Patients show stronger appetite suppression, greater insulin secretion stimulation, and faster weight loss compared to non-carriers.',
    'Start at 0.25 mg weekly (50% of standard 0.5 mg). Titrate every 4 weeks instead of 2. Monitor for nausea, early satiety, and hypoglycemia if on concurrent sulfonylureas.',
    'Enhanced GLP-1 sensitivity amplifies GI side effects (nausea, vomiting, diarrhea). Risk of pancreatitis may be slightly elevated. Rapid weight loss in first 4 weeks may require nutritional counseling to prevent muscle wasting.',
    FALSE,
    NULL,
    ARRAY['hsa04911'],
    ARRAY['25533189', '27383131']
),

-- Row 14: GLP1R / rs3765467 / GLP-1 Agonist — BLUNTED
(
    'GLP1R',
    'SNP',
    'rs3765467',
    'GLP1R reduced function variant',
    'Semaglutide',
    'GLP-1 Agonist',
    'GLP1R',
    'blunted',
    'B',
    'rs3765467 reduces GLP-1 receptor coupling efficiency, requiring higher GLP-1 concentrations to achieve standard signaling. Patients may report subtherapeutic appetite suppression and slower weight loss at standard doses.',
    'Start at standard dose (0.5 mg weekly). If inadequate response at 8 weeks, escalate to 1.0 mg. Consider combination with tirzepatide (dual GLP-1/GIP) for additive effect.',
    'Dose escalation increases nausea risk. Monitor for GI tolerance at each increase. Consider concurrent antiemetic if dose escalation needed.',
    FALSE,
    NULL,
    ARRAY['hsa04911'],
    ARRAY['25533189', '28578325']
),

-- Row 15: GLP1R / rs6923761 / Tirzepatide — ENHANCED
(
    'GLP1R',
    'SNP',
    'rs6923761',
    'GLP1R sensitivity variant (Ala316Thr)',
    'Tirzepatide',
    'Dual GLP-1/GIP Agonist',
    'GLP1R',
    'enhanced',
    'A',
    'Tirzepatide''s dual GLP-1/GIP mechanism amplifies the GLP1R sensitivity effect. rs6923761 carriers on tirzepatide show roughly 30% greater weight loss than non-carriers in pharmacogenomic substudies. Both incretin pathways contribute synergistically.',
    'Start at 2.5 mg weekly (standard starting dose is appropriate given dual mechanism). Extend titration intervals to 6 weeks between increases. Target dose may be lower than population average.',
    'Tirzepatide''s GI profile may be more tolerable than pure GLP-1 agonists due to GIP component. However, enhanced GLP-1 sensitivity still increases nausea risk. Monitor thyroid function (GLP-1 class carries medullary thyroid carcinoma warning).',
    FALSE,
    NULL,
    ARRAY['hsa04911'],
    ARRAY['35658024', '36519438']
),

-- Row 16: CYP19A1 / rs700519 / Estradiol — BLUNTED
(
    'CYP19A1',
    'SNP',
    'rs700519',
    'Aromatase decreased activity variant',
    'Estradiol (transdermal)',
    'Estrogen',
    'ESR1',
    'blunted',
    'B',
    'rs700519 reduces aromatase (CYP19A1) enzyme activity, decreasing endogenous estrogen synthesis. Exogenous estradiol bypasses this deficiency but the variant signals underlying estrogen deficiency that may require higher replacement doses.',
    'Consider starting at higher end of standard range (0.075 mg/day patch instead of 0.05 mg). Monitor serum estradiol at 6 weeks to verify therapeutic levels. May need dose escalation earlier than average.',
    'Higher estradiol doses increase VTE and breast cancer risk modestly. Balance symptom relief against cardiovascular risk profile. Consider adding progesterone if intact uterus.',
    FALSE,
    NULL,
    ARRAY['hsa00140', 'hsa04913'],
    ARRAY['19276230', '22987536']
),

-- Row 17: COMT / rs4680 / Estradiol — ENHANCED
(
    'COMT',
    'SNP',
    'rs4680',
    'Val158Met (reduced COMT activity)',
    'Estradiol (transdermal)',
    'Estrogen',
    'ESR1',
    'enhanced',
    'B',
    'COMT Val158Met (rs4680) reduces catechol-O-methyltransferase activity by 3-4x, slowing estrogen catabolism. Exogenous estradiol has longer half-life and higher effective concentration. Patients may experience enhanced estrogenic effects at standard doses.',
    'Start at lower range of standard dosing (0.025-0.0375 mg/day patch). Monitor for breast tenderness, bloating, mood changes — early signs of estrogen excess. Adjust based on symptom response rather than serum levels alone.',
    'Reduced COMT activity increases catechol estrogen intermediates (2-OH, 4-OH estrone), some of which are potentially genotoxic. Consider DIM or I3C supplementation to support alternative estrogen metabolism pathways.',
    FALSE,
    NULL,
    ARRAY['hsa04913', 'hsa00140'],
    ARRAY['17487217', '22407345']
),

-- Row 18: PGR / rs1042838 / Progesterone — ENHANCED
(
    'PGR',
    'SNP',
    'rs1042838',
    'Progesterone receptor promoter +331 A/G',
    'Micronized Progesterone',
    'Progestogen',
    'PGR',
    'enhanced',
    'B',
    'rs1042838 +331 A/G promoter variant increases PGR transcription, producing higher progesterone receptor density. Standard doses of micronized progesterone achieve enhanced downstream effects including endometrial protection and anxiolytic activity.',
    'Standard dose (200 mg oral at bedtime) is appropriate. Watch for excessive sedation (progesterone metabolite allopregnanolone has GABAergic effects). Consider 100 mg if sedation is problematic.',
    'Enhanced progesterone signaling may amplify mood effects (both positive anxiolytic and negative depressive). Monitor mood closely in first 2 weeks. Consider vaginal route if oral sedation is excessive.',
    FALSE,
    NULL,
    ARRAY['hsa04913'],
    ARRAY['18281658', '21300408']
),

-- Row 19: OXTR / rs53576 / Oxytocin — ENHANCED
(
    'OXTR',
    'SNP',
    'rs53576',
    'OXTR GG genotype (high expression)',
    'Oxytocin (intranasal)',
    'Neuropeptide',
    'OXTR',
    'enhanced',
    'B',
    'rs53576 GG genotype is associated with higher OXTR expression and enhanced oxytocin signaling. Intranasal oxytocin produces stronger social bonding, empathy, and anxiolytic effects in GG carriers. May also enhance uterine sensitivity.',
    'Start at standard dose (24 IU intranasal). Monitor for enhanced emotional response. If used perinatally, be aware of potentially stronger uterine contractility.',
    'Enhanced oxytocin response may produce emotional over-reactivity in some patients. Intranasal administration bypasses blood-brain barrier — effects are rapid but duration limited (30-60 min).',
    FALSE,
    NULL,
    ARRAY['hsa04921'],
    ARRAY['22123970', '25107577']
),

-- Row 20: MC4R / rs17782313 / Setmelanotide — BLUNTED
(
    'MC4R',
    'SNP',
    'rs17782313',
    'MC4R near-gene variant (reduced signaling)',
    'Setmelanotide',
    'Melanocortin Agonist',
    'MC4R',
    'blunted',
    'B',
    'rs17782313 is associated with reduced MC4R signaling efficiency and increased obesity risk. Setmelanotide directly targets MC4R for appetite suppression, but reduced receptor function means higher doses or longer treatment may be needed.',
    'Standard dosing protocol applies. Expect slower appetite response (4-6 weeks instead of 2-3 weeks). If minimal response at week 8, dose escalation per prescribing guidelines.',
    'Setmelanotide can cause skin hyperpigmentation (melanocortin cross-activation of MC1R). Sexual side effects (spontaneous erections in males) are common. Monitor skin changes and counsel patient.',
    FALSE,
    NULL,
    ARRAY['hsa04024'],
    ARRAY['30929901', '33497170']
),

-- Row 21: ESR1 / rs2228480 / Raloxifene (SERM) — ENHANCED
(
    'ESR1',
    'SNP',
    'rs2228480',
    'ESR1 increased expression variant',
    'Raloxifene',
    'SERM',
    'ESR1',
    'enhanced',
    'A',
    'rs2228480 increases ESR1 expression, enhancing sensitivity to SERMs. Raloxifene selectively activates ESR1 in bone (protective) while blocking in breast (protective). Enhanced ESR1 expression amplifies both bone protection and breast cancer risk reduction.',
    'Standard dose (60 mg daily). Enhanced bone density response expected. Monitor for hot flash exacerbation (raloxifene can worsen vasomotor symptoms in some ESR1-high patients).',
    'SERMs may worsen hot flashes in menopause (20-30% of patients). Enhanced ESR1 expression may amplify this effect. VTE risk is inherent to raloxifene (class effect). Screen for VTE history.',
    FALSE,
    NULL,
    ARRAY['hsa04915', 'hsa04917'],
    ARRAY['15166096', '20375405']
),

-- Row 22: FSHR / rs6166 / Gonadotropins — BLUNTED
(
    'FSHR',
    'SNP',
    'rs6166',
    'FSHR Asn680Ser (reduced function)',
    'Recombinant FSH',
    'Gonadotropin',
    'FSHR',
    'blunted',
    'B',
    'rs6166 Asn680Ser reduces FSH receptor sensitivity, requiring higher FSH concentrations for equivalent ovarian stimulation. Relevant for fertility preservation or ovarian function assessment in perimenopause.',
    'Higher starting dose of recombinant FSH may be needed (225 IU instead of 150 IU). Closer monitoring with serial ultrasound. Expect slower follicular response.',
    'Higher FSH doses increase ovarian hyperstimulation risk. Monitor estradiol levels closely during stimulation cycles.',
    FALSE,
    NULL,
    ARRAY['hsa04912'],
    ARRAY['16835214', '24412074']
),

-- Row 23: GPER1 / rs3808350 / Estradiol (rapid signaling) — ENHANCED
(
    'GPER1',
    'SNP',
    'rs3808350',
    'GPER1 increased expression variant',
    'Estradiol (transdermal)',
    'Estrogen',
    'GPER1',
    'enhanced',
    'B',
    'GPER1 mediates rapid, non-genomic estrogen signaling — cardiovascular protection, vasodilation, neuroprotection. rs3808350 increases GPER1 density, amplifying these rapid protective effects of exogenous estradiol.',
    'Standard estradiol dosing. Patient may experience enhanced cardiovascular protective effects. No dose adjustment needed specifically for GPER1 variant.',
    'GPER1 activation can lower blood pressure via vasodilation. Monitor BP in patients on antihypertensives to avoid hypotension.',
    FALSE,
    NULL,
    ARRAY['hsa04915'],
    ARRAY['21148284', '25684486']
),

-- Row 24: HTR1A / rs1042173 / SSRIs (menopause mood) — ENHANCED
(
    'HTR1A',
    'SNP',
    'rs1042173',
    'HTR1A C-1019G promoter variant',
    'Paroxetine (low-dose)',
    'SSRI (off-label for hot flashes)',
    'HTR1A',
    'enhanced',
    'B',
    'rs1042173 affects serotonin 1A receptor expression. Low-dose paroxetine (7.5 mg, FDA-approved for vasomotor symptoms) targets serotonergic signaling to reduce hot flashes. Variant may predict enhanced response to serotonergic interventions.',
    'Start at FDA-approved 7.5 mg/day dose. Monitor for enhanced anxiolytic effect. If mood improvement is rapid (< 1 week), likely a strong responder.',
    'Low-dose SSRIs can cause sexual dysfunction, weight gain, and discontinuation syndrome. At 7.5 mg these are less common than therapeutic antidepressant doses. Taper slowly if discontinuing.',
    FALSE,
    NULL,
    ARRAY['hsa04726'],
    ARRAY['28741234', '30102412']
),

-- Row 25: IL6 / rs1800795 / Anti-inflammatory peptides — ENHANCED
(
    'IL6',
    'SNP',
    'rs1800795',
    'IL-6 promoter -174 G/C (high IL-6 producer)',
    'BPC-157',
    'Anti-inflammatory Peptide',
    'IL6R',
    'enhanced',
    'B',
    'rs1800795 GG genotype produces higher baseline IL-6 levels, indicating a pro-inflammatory phenotype. BPC-157 has demonstrated anti-inflammatory properties in preclinical models. Patients with high IL-6 production may derive greater benefit from anti-inflammatory peptide therapy.',
    'Standard dosing protocol. Expect enhanced anti-inflammatory response. Monitor CRP and IL-6 at baseline and 4 weeks to quantify response.',
    'BPC-157 is not FDA-approved. Evidence is primarily preclinical (rodent models). Inform patient of limited human clinical data. Monitor liver function as peptide is orally bioavailable.',
    FALSE,
    NULL,
    ARRAY['hsa04630'],
    ARRAY['28652587', '31492561']
),

-- Row 26: TNF / rs1799724 / Anti-inflammatory approach — ENHANCED
(
    'TNF',
    'SNP',
    'rs1799724',
    'TNF-alpha -308 G/A (high TNF producer)',
    'Thymosin Alpha-1',
    'Immunomodulatory Peptide',
    'TNFR1',
    'enhanced',
    'B',
    'rs1799724 is associated with increased TNF-alpha production, contributing to systemic inflammation. Thymosin alpha-1 modulates immune response by rebalancing Th1/Th2 cytokine profiles. High TNF producers may show greater immunomodulatory benefit.',
    'Standard dosing (1.6 mg subcutaneous 2x/week). Monitor inflammatory markers at baseline and 6 weeks. Enhanced immunomodulatory effect expected in high-TNF genotype patients.',
    'Thymosin alpha-1 may potentiate immune responses; caution in autoimmune conditions. Monitor for flu-like symptoms in first week. Injection site reactions are common.',
    FALSE,
    ARRAY['TNF'],
    ARRAY['hsa04668'],
    ARRAY['29698857', '31156265']
),

-- Row 27: CRP / rs2794520 / Systemic inflammation baseline — ENHANCED (monitoring)
(
    'CRP',
    'SNP',
    'rs2794520',
    'CRP promoter high-expression variant',
    'Omega-3 (EPA/DHA)',
    'Anti-inflammatory Supplement',
    NULL,
    'enhanced',
    'C',
    'rs2794520 increases baseline CRP production, indicating a genetically-driven pro-inflammatory state. High-dose omega-3 (EPA > 1.8g/day) has robust evidence for CRP reduction. Genetic high-CRP patients show greater absolute CRP reduction with omega-3.',
    'EPA-dominant omega-3 at 2-4g/day. Monitor CRP at baseline and 8 weeks. Expect 20-30% CRP reduction in high-CRP genotype. Combine with anti-inflammatory diet for additive effect.',
    'High-dose omega-3 increases bleeding time. Caution with anticoagulants. GI side effects (fishy burps, loose stool) common at high doses. Consider enteric-coated formulation.',
    FALSE,
    NULL,
    ARRAY[]::TEXT[],
    ARRAY['24062427', '28245826']
),

-- Row 28: SLC6A4 / rs1360780 / SSRI response for hot flashes — ENHANCED
(
    'SLC6A4',
    'SNP',
    'rs1360780',
    '5-HTTLPR long allele (high transporter expression)',
    'Venlafaxine (low-dose)',
    'SNRI (off-label for hot flashes)',
    'SLC6A4',
    'enhanced',
    'B',
    'Long allele of 5-HTTLPR (tagged by rs1360780) increases serotonin transporter expression. Low-dose venlafaxine (37.5-75 mg) targets serotonin reuptake to reduce vasomotor symptoms. High transporter expression predicts better SNRI response.',
    'Start at 37.5 mg/day. Titrate to 75 mg if needed at 2 weeks. Monitor blood pressure (SNRI class effect). Enhanced serotonergic response expected.',
    'Venlafaxine withdrawal syndrome if discontinued abruptly — always taper. May increase blood pressure at higher doses. Sexual dysfunction possible even at low doses.',
    FALSE,
    NULL,
    ARRAY['hsa04726'],
    ARRAY['21525519', '26847258']
),

-- Row 29: PPARG / rs1801282 / Insulin sensitizers — ENHANCED
(
    'PPARG',
    'SNP',
    'rs1801282',
    'Pro12Ala (increased insulin sensitivity)',
    'Metformin',
    'Insulin Sensitizer',
    'AMPK',
    'enhanced',
    'B',
    'rs1801282 Pro12Ala increases PPARG transcriptional activity, improving baseline insulin sensitivity. Metformin acts via AMPK pathway to reduce hepatic glucose output. Pro12Ala carriers show enhanced metformin response due to synergistic insulin-sensitizing mechanisms.',
    'Standard dosing (500 mg BID, titrate to 1000 mg BID). Enhanced glycemic response expected — may achieve target HbA1c at lower doses. Monitor for hypoglycemia if on concurrent sulfonylureas.',
    'GI side effects (diarrhea, abdominal pain) common in first 2 weeks — use extended-release formulation. B12 malabsorption with long-term use. Monitor B12 annually.',
    FALSE,
    NULL,
    ARRAY['hsa04152', 'hsa04930'],
    ARRAY['11132768', '27053137']
),

-- Row 30: VDR / rs2228570 / Vitamin D + Calcium (bone health) — BLUNTED
(
    'VDR',
    'SNP',
    'rs2228570',
    'VDR FokI polymorphism (reduced function)',
    'Vitamin D3 + Calcium',
    'Bone Health Supplement',
    'VDR',
    'blunted',
    'B',
    'rs2228570 FokI polymorphism produces a shorter VDR protein with reduced transcriptional activity. Vitamin D3 supplementation may be less effective at standard doses for calcium absorption and bone density maintenance in postmenopausal women.',
    'Higher vitamin D3 dose may be needed (2000-4000 IU/day instead of 800-1000 IU). Monitor 25-OH-vitamin D levels at 8 weeks. Target serum level 40-60 ng/mL. Consider calcium citrate (better absorption than carbonate).',
    'High-dose vitamin D increases calcium absorption — monitor for hypercalcemia if on calcium supplements. Risk of kidney stones with high calcium + vitamin D. Monitor serum calcium annually.',
    FALSE,
    NULL,
    ARRAY[]::TEXT[],
    ARRAY['16172156', '24486198']
),

-- =========================================================================
-- ROWS 31-50: Additional genotype-peptide combinations for demo coverage
-- =========================================================================

-- Row 31: ESR1 / rs9340799 / Tamoxifen (breast cancer prevention) — ENHANCED
(
    'ESR1', 'SNP', 'rs9340799', 'ESR1 XbaI polymorphism',
    'Tamoxifen', 'SERM', 'ESR1', 'enhanced', 'A',
    'rs9340799 XbaI polymorphism in ESR1 intron 1 is associated with altered receptor expression and enhanced SERM binding. Tamoxifen blocks ESR1 in breast tissue while activating in bone — enhanced ESR1 expression amplifies both effects.',
    'Standard tamoxifen dose (20 mg/day). Enhanced breast cancer risk reduction expected. Monitor for endometrial thickening (SERM class effect).',
    'Tamoxifen increases endometrial cancer risk. Hot flashes common (30-40%). VTE risk elevated. Annual gynecologic exam required.',
    FALSE, NULL, ARRAY['hsa04915'], ARRAY['15166096', '18042754']
),

-- Row 32: ESR2 / rs4986938 / Phytoestrogens — ENHANCED
(
    'ESR2', 'SNP', 'rs4986938', 'ESR2 AluI polymorphism',
    'Genistein (Phytoestrogen)', 'Isoflavone', 'ESR2', 'enhanced', 'C',
    'ESR2 preferentially binds phytoestrogens. rs4986938 increases ESR2 expression, amplifying isoflavone-mediated effects. Genistein is a selective ESR2 agonist with anti-proliferative, neuroprotective, and anxiolytic properties.',
    'Genistein 40-80 mg/day from soy-derived supplements. Monitor for GI tolerance. Expect modest hot flash reduction (20-30% in ESR2-high genotypes).',
    'Limited evidence vs. HRT. Not a substitute for estradiol in severe symptoms. May interact with thyroid medication absorption.',
    FALSE, NULL, ARRAY['hsa04915'], ARRAY['17473952', '21715508']
),

-- Row 33: CYP2D6 / rs3892097 / Tamoxifen metabolism — BLUNTED
(
    'CYP2D6', 'SNP', 'rs3892097', 'CYP2D6*4 poor metabolizer',
    'Tamoxifen', 'SERM', 'ESR1', 'blunted', 'A',
    'CYP2D6*4 (rs3892097) abolishes enzyme activity. Tamoxifen is a prodrug requiring CYP2D6 conversion to active metabolite endoxifen. Poor metabolizers achieve only 20-30% of normal endoxifen levels, drastically reducing efficacy.',
    'CONTRAINDICATED or switch to aromatase inhibitor (anastrozole, letrozole) which does not require CYP2D6 activation. If tamoxifen must be used, consider endoxifen level monitoring.',
    'Aromatase inhibitors cause joint pain, bone density loss, and fatigue. Monitor bone density if switching. Tamoxifen in poor metabolizers provides minimal benefit for breast cancer risk reduction.',
    FALSE, ARRAY['CYP2D6'], ARRAY['hsa00982'], ARRAY['16923433', '22395583']
),

-- Row 34: MTHFR / rs1801133 / Methylfolate — ENHANCED
(
    'MTHFR', 'SNP', 'rs1801133', 'MTHFR C677T (reduced enzyme activity)',
    'L-Methylfolate', 'Vitamin/Nutraceutical', NULL, 'enhanced', 'B',
    'rs1801133 C677T reduces MTHFR enzyme activity by 30-70%, impairing folate metabolism and methylation capacity. L-methylfolate bypasses MTHFR and provides active folate directly. TT homozygotes show 30% elevated homocysteine and impaired neurotransmitter synthesis.',
    'L-methylfolate 15 mg/day (prescription Deplin) or 1-5 mg/day (OTC). Monitor homocysteine at baseline and 8 weeks. Expect improved mood, energy, and cognitive function in deficient patients.',
    'L-methylfolate may unmask B12 deficiency — check B12 before starting. High-dose folate can mask pernicious anemia. Some patients report overstimulation or anxiety at high doses.',
    FALSE, NULL, ARRAY[]::TEXT[], ARRAY['22559284', '24637015']
),

-- Row 35: FTO / rs9939609 / GLP-1 weight loss response — ENHANCED
(
    'FTO', 'SNP', 'rs9939609', 'FTO obesity risk variant',
    'Semaglutide', 'GLP-1 Agonist', 'GLP1R', 'enhanced', 'B',
    'rs9939609 AA genotype increases obesity risk by 30-40%. Semaglutide produces 15-17% weight loss in clinical trials, but FTO risk carriers show greater absolute weight loss due to higher baseline BMI and enhanced metabolic response to GLP-1 signaling.',
    'Standard semaglutide dosing (start 0.25 mg, titrate to 1.0-2.4 mg). FTO carriers may achieve above-average weight loss. Monitor for nutritional deficiencies during rapid weight loss phase.',
    'Greater absolute weight loss increases risk of gallstones, hair loss, and muscle wasting. Ensure adequate protein intake (1.2-1.6g/kg/day). Consider resistance exercise program.',
    FALSE, NULL, ARRAY['hsa04920'], ARRAY['17434869', '34706925']
),

-- Row 36: TCF7L2 / rs7903146 / Metformin + GLP-1 combo — ENHANCED
(
    'TCF7L2', 'SNP', 'rs7903146', 'TCF7L2 diabetes risk variant',
    'Metformin + Semaglutide (combination)', 'Combination Therapy', 'GLP1R', 'enhanced', 'A',
    'rs7903146 is the strongest common genetic risk factor for type 2 diabetes (OR 1.35 per T allele). TCF7L2 variants impair incretin signaling and beta-cell function. Combined metformin (insulin sensitizer) + GLP-1 agonist (incretin mimetic) addresses both pathways simultaneously.',
    'Metformin 500 mg BID + semaglutide 0.25 mg weekly. Titrate both independently. Combination therapy in TCF7L2 carriers may achieve HbA1c targets 6-8 weeks faster than monotherapy.',
    'Combination increases GI side effect risk (additive nausea). Start metformin first (1-2 weeks), then add GLP-1 agonist. Monitor for hypoglycemia if on sulfonylureas.',
    FALSE, NULL, ARRAY['hsa04152', 'hsa04911'], ARRAY['16415884', '28813709']
),

-- Row 37: BDNF / rs6265 / Cognitive support peptides — BLUNTED
(
    'BDNF', 'SNP', 'rs6265', 'BDNF Val66Met (reduced secretion)',
    'Semax (nootropic peptide)', 'Neuropeptide', NULL, 'enhanced', 'C',
    'rs6265 Val66Met reduces activity-dependent BDNF secretion by 25-30%, impairing neuroplasticity and cognitive resilience. Semax is a synthetic ACTH(4-10) analogue that upregulates BDNF expression. Met carriers may derive greater relative cognitive benefit.',
    'Semax 0.1% nasal spray, 2-3 drops per nostril 2x/day. Monitor cognitive function (trail-making test, verbal fluency) at baseline and 4 weeks. Enhanced neurotrophin response expected in Met carriers.',
    'Semax is not FDA-approved (available as research peptide). Evidence primarily from Russian clinical studies. Limited Western peer-reviewed data. Inform patient of regulatory status.',
    FALSE, NULL, ARRAY[]::TEXT[], ARRAY['16138786', '24237484']
),

-- Row 38: APOE / rs429358 / Estradiol VTE risk — CONTRAINDICATED
(
    'APOE', 'SNP', 'rs429358', 'APOE4 carrier (epsilon 4 allele)',
    'Estradiol (oral)', 'Estrogen', 'ESR1', 'contraindicated', 'A',
    'APOE4 carriers have 3-4x increased venous thromboembolism risk with oral estrogen therapy. First-pass hepatic metabolism of oral estradiol activates coagulation cascade, and APOE4 genotype compounds this prothrombotic effect.',
    'ORAL estradiol is CONTRAINDICATED in APOE4 carriers. Switch to transdermal estradiol (bypasses first-pass metabolism, negligible VTE risk). If oral route absolutely necessary, add anticoagulation assessment and D-dimer monitoring.',
    'Transdermal route has minimal VTE risk even in APOE4 carriers — this is a route-specific contraindication, not an estrogen-class contraindication. Monitor for DVT symptoms regardless of route. Screen family history for thrombophilia.',
    TRUE, ARRAY['APOE'], ARRAY['hsa04915'], ARRAY['15626905', '19506141']
),

-- Row 39: KCNJ11 / rs5219 / Sulfonylureas — ENHANCED
(
    'KCNJ11', 'SNP', 'rs5219', 'KCNJ11 E23K (altered channel function)',
    'Glimepiride', 'Sulfonylurea', 'KCNJ11', 'enhanced', 'B',
    'rs5219 E23K alters KATP channel sensitivity in pancreatic beta cells. Sulfonylureas close KATP channels to stimulate insulin secretion. E23K carriers show enhanced insulin secretory response to sulfonylureas due to altered channel gating kinetics.',
    'Start at lowest dose (1 mg/day). Enhanced insulin secretion expected — higher hypoglycemia risk. Titrate slowly with glucose monitoring. Consider CGM for first 2 weeks.',
    'Sulfonylureas cause weight gain (2-4 kg average). Hypoglycemia risk is real and dose-dependent. Not first-line for obesity-associated T2D (prefer GLP-1 or SGLT2). Consider only if GLP-1 is contraindicated.',
    FALSE, NULL, ARRAY['hsa04930'], ARRAY['18369795', '24722495']
),

-- Row 40: SLC22A1 / rs622342 / Metformin transport — BLUNTED
(
    'SLC22A1', 'SNP', 'rs622342', 'OCT1 reduced function variant',
    'Metformin', 'Insulin Sensitizer', 'AMPK', 'blunted', 'B',
    'SLC22A1 encodes OCT1 (organic cation transporter 1), the primary hepatic uptake transporter for metformin. rs622342 reduces OCT1 activity by 20-40%, decreasing hepatic metformin concentration and reducing glucose-lowering efficacy.',
    'Standard starting dose may be insufficient. If HbA1c target not met at 8 weeks on 2000 mg/day, switch to or add GLP-1 agonist rather than dose-escalating metformin. Consider OCT1-independent alternatives.',
    'Reduced hepatic uptake paradoxically increases plasma metformin levels (higher GI side effects, higher lactic acidosis risk at high doses). Do not exceed 2000 mg/day in poor OCT1 function patients.',
    FALSE, NULL, ARRAY['hsa04152'], ARRAY['19159735', '22306722']
),

-- Row 41: CLOCK / rs1801260 / Melatonin — ENHANCED
(
    'CLOCK', 'SNP', 'rs1801260', 'CLOCK 3111T/C circadian variant',
    'Melatonin (extended-release)', 'Chronobiotic', 'MTNR1A', 'enhanced', 'B',
    'rs1801260 in the CLOCK gene disrupts circadian rhythm regulation, contributing to sleep onset insomnia common in perimenopause. Extended-release melatonin targets MT1/MT2 receptors to reset circadian phase. CLOCK variant carriers show greater phase-shifting response.',
    'Extended-release melatonin 2 mg, 30-60 min before desired sleep time. Avoid bright light exposure after dosing. Enhanced circadian entrainment expected in CLOCK variant carriers.',
    'Melatonin can cause morning grogginess at higher doses. Avoid in patients on immunosuppressants (melatonin has immunomodulatory effects). May interact with anticoagulants.',
    FALSE, NULL, ARRAY[]::TEXT[], ARRAY['17998023', '24863153']
),

-- Row 42: HTR2A / rs6313 / SSRI for vasomotor symptoms — ENHANCED
(
    'HTR2A', 'SNP', 'rs6313', 'HTR2A T102C promoter variant',
    'Escitalopram (low-dose)', 'SSRI (off-label for hot flashes)', 'HTR2A', 'enhanced', 'B',
    'rs6313 T102C alters serotonin 2A receptor density. Low-dose escitalopram (10-20 mg) reduces hot flash frequency by 40-60% in clinical trials. T allele carriers show enhanced serotonergic response and greater vasomotor symptom relief.',
    'Start at 10 mg/day. If insufficient at 4 weeks, increase to 20 mg. Enhanced hot flash reduction expected in T allele carriers. Monitor for QTc prolongation (rare at low doses).',
    'SSRIs can cause sexual dysfunction, weight gain, and emotional blunting. Taper slowly if discontinuing (SSRI discontinuation syndrome). QTc monitoring recommended if on other QT-prolonging drugs.',
    FALSE, NULL, ARRAY['hsa04726'], ARRAY['22198456', '25677412']
),

-- Row 43: ADRB2 / rs1042713 / Beta-agonist response — BLUNTED
(
    'ADRB2', 'SNP', 'rs1042713', 'ADRB2 Arg16Gly (receptor downregulation)',
    'Terbutaline', 'Beta-2 Agonist', 'ADRB2', 'blunted', 'B',
    'rs1042713 Gly16 variant causes enhanced receptor downregulation with chronic beta-2 agonist exposure. Initial response may be normal but tachyphylaxis develops faster. Relevant for patients using beta-agonists for premature labor or asthma management during perimenopause.',
    'Standard initial dosing. Expect faster tolerance development. Consider switching to alternative tocolytic or adding low-dose corticosteroid to reduce receptor downregulation.',
    'Tachyphylaxis to beta-agonists in Gly16 carriers may be mistaken for treatment failure. Reassess response at 48 hours. Do not simply increase dose — switch class.',
    FALSE, NULL, ARRAY[]::TEXT[], ARRAY['12612583', '18424453']
),

-- Row 44: NR3C1 / rs41423247 / Cortisol response — ENHANCED
(
    'NR3C1', 'SNP', 'rs41423247', 'Glucocorticoid receptor BclI variant',
    'Hydrocortisone (stress-dose)', 'Glucocorticoid', 'NR3C1', 'enhanced', 'B',
    'rs41423247 BclI polymorphism in the glucocorticoid receptor gene increases receptor sensitivity. Patients show enhanced cortisol-mediated effects including immunosuppression, metabolic changes, and HPA axis suppression at standard doses.',
    'Use lowest effective dose. Enhanced HPA suppression expected — taper slowly. Monitor for cushingoid features if on chronic low-dose therapy. Stress-dose protocols may need downward adjustment.',
    'Enhanced glucocorticoid sensitivity increases risk of adrenal suppression, osteoporosis, diabetes, and immunosuppression. Monitor bone density, glucose, and adrenal function regularly.',
    FALSE, NULL, ARRAY[]::TEXT[], ARRAY['14766726', '19451174']
),

-- Row 45: SLCO1B1 / rs4149056 / Statin intolerance — ENHANCED risk
(
    'SLCO1B1', 'SNP', 'rs4149056', 'SLCO1B1*5 (reduced hepatic uptake)',
    'Rosuvastatin', 'Statin', 'HMGCR', 'blunted', 'A',
    'rs4149056 reduces OATP1B1 hepatic transporter function, increasing systemic statin exposure by 2-3x. Elevated statin levels cause myopathy and rhabdomyolysis risk. Relevant for cardiovascular risk management in postmenopausal women.',
    'Reduce rosuvastatin dose to 5-10 mg (standard is 10-20 mg). Avoid simvastatin 80 mg. Consider pravastatin (less OATP1B1 dependent) as alternative. CK monitoring at baseline and 6 weeks.',
    'Statin myopathy ranges from mild muscle aches (5-10% prevalence) to rhabdomyolysis (rare but serious). CC homozygotes have 17x myopathy risk on simvastatin. Educate patient on muscle symptom reporting.',
    FALSE, ARRAY['SLCO1B1'], ARRAY[]::TEXT[], ARRAY['18650507', '24190015']
),

-- Row 46: OPRM1 / rs1799971 / Naltrexone response — BLUNTED
(
    'OPRM1', 'SNP', 'rs1799971', 'OPRM1 Asn40Asp (altered mu-opioid receptor)',
    'Low-dose Naltrexone (LDN)', 'Opioid Antagonist', 'OPRM1', 'enhanced', 'B',
    'rs1799971 Asp40 variant alters mu-opioid receptor binding affinity. Low-dose naltrexone (1.5-4.5 mg) produces anti-inflammatory and immunomodulatory effects via transient opioid receptor blockade. Asp40 carriers show altered endorphin rebound dynamics.',
    'LDN 1.5 mg at bedtime, titrate to 4.5 mg over 2 weeks. Asp40 carriers may need slower titration. Monitor for vivid dreams (common first week). Enhanced immune modulation expected.',
    'LDN is off-label use. Contraindicated in patients on opioid medications (precipitates withdrawal). May cause insomnia, headache, or nausea initially. Avoid in active opioid use disorder.',
    FALSE, NULL, ARRAY[]::TEXT[], ARRAY['12809961', '24365484']
),

-- Row 47: GLP1R / rs6923761 + APOE4 / GLP-1 with VTE monitoring — ENHANCED with safety
(
    'GLP1R', 'SNP', 'rs6923761', 'GLP1R sensitivity + APOE4 carrier (combination)',
    'Liraglutide', 'GLP-1 Agonist', 'GLP1R', 'enhanced', 'A',
    'Combined GLP1R sensitivity (rs6923761) with APOE4 carrier status creates enhanced peptide response with concurrent cardiovascular monitoring needs. Liraglutide has demonstrated cardiovascular benefit (LEADER trial) which may be particularly relevant for APOE4 carriers at elevated CVD risk.',
    'Liraglutide 0.6 mg/day (reduced start due to GLP1R sensitivity). Titrate to 1.2-1.8 mg over 4 weeks. Add cardiovascular monitoring given APOE4 status. Check lipid panel at baseline and 12 weeks.',
    'Liraglutide carries medullary thyroid carcinoma warning (MTC). Contraindicated in personal/family history of MTC or MEN2. Monitor thyroid function. GI side effects common during titration.',
    FALSE, ARRAY['APOE'], ARRAY['hsa04911'], ARRAY['27295427', '32333090']
),

-- Row 48: TPMT / rs1800460 / Azathioprine (autoimmune) — CONTRAINDICATED
(
    'TPMT', 'SNP', 'rs1800460', 'TPMT*3B (reduced enzyme activity)',
    'Azathioprine', 'Immunosuppressant', NULL, 'contraindicated', 'A',
    'TPMT*3B (rs1800460) reduces thiopurine methyltransferase activity. Azathioprine is metabolized by TPMT — poor metabolizers accumulate toxic thioguanine nucleotides causing severe myelosuppression (potentially fatal pancytopenia).',
    'CONTRAINDICATED at standard doses in TPMT poor metabolizers. If azathioprine required, reduce dose by 50-90% and monitor CBC weekly for 8 weeks. Consider mycophenolate mofetil as alternative immunosuppressant.',
    'TPMT testing is considered standard of care before azathioprine initiation by CPIC guidelines. Fatal myelosuppression has occurred in untested poor metabolizers. This is one of the most clinically validated pharmacogenomic interactions.',
    TRUE, ARRAY['TPMT'], ARRAY[]::TEXT[], ARRAY['10534374', '21270794']
),

-- Row 49: UGT1A1 / rs8175347 / Irinotecan (cancer therapy) — BLUNTED metabolism
(
    'UGT1A1', 'STR_repeat', 'rs8175347', 'UGT1A1*28 (TA repeat, reduced conjugation)',
    'Irinotecan', 'Chemotherapy', NULL, 'contraindicated', 'A',
    'UGT1A1*28 (7 TA repeats) reduces UDP-glucuronosyltransferase activity by 70%. Irinotecan''s active metabolite SN-38 is glucuronidated by UGT1A1. Poor metabolizers accumulate toxic SN-38 levels causing severe neutropenia and diarrhea.',
    'DOSE REDUCTION REQUIRED: Reduce irinotecan by 25-30% in UGT1A1*28 homozygotes. FDA label includes UGT1A1 testing recommendation. Heterozygotes may tolerate standard doses with close monitoring.',
    'Grade 4 neutropenia and grade 3-4 diarrhea occur in 50% of *28/*28 homozygotes at standard doses. This is an FDA-labeled pharmacogenomic interaction. Genotyping is recommended before irinotecan initiation.',
    TRUE, ARRAY['UGT1A1'], ARRAY[]::TEXT[], ARRAY['15520394', '19636341']
),

-- Row 50: ESR1 / rs2228480 + CYP19A1 / Combined estrogen pathway — ENHANCED
(
    'ESR1', 'SNP', 'rs2228480', 'ESR1 high-expression + CYP19A1 normal (optimal HRT candidate)',
    'Estradiol + Progesterone (combined HRT)', 'Combined HRT', 'ESR1', 'enhanced', 'A',
    'Combination of ESR1 rs2228480 (high receptor expression) with intact CYP19A1 aromatase function creates an optimal estrogen-responsive phenotype. Patient produces estrogen normally and has enhanced receptor sensitivity — ideal candidate for standard-dose combined HRT.',
    'Standard combined HRT: estradiol 0.05 mg/day transdermal + micronized progesterone 200 mg/day oral (if uterus present). Expect excellent symptom relief. Monitor at 3 months for dose optimization.',
    'Combined HRT carries established risks: modest breast cancer increase after 5+ years, VTE risk (route-dependent), endometrial protection requires adequate progesterone. Annual mammogram and breast exam required.',
    FALSE, NULL, ARRAY['hsa04915', 'hsa00140'], ARRAY['12072556', '28707627']
);

COMMIT;
