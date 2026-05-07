# Qualitative Case Studies

These cases are selected from the canonical English-input reliability outputs. Assisted adjudication is not used.

## Overview

| Case | Group | Human | Benchmark | Old weak maj. | Strict maj. | Selected unreliable-score row | Paper use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AUDIT-018 | Entity/title ambiguity | unfaithful | faithful | unfaithful | unfaithful | target_verdict_unreliable_strict / old_weak_qwen36plus20260402 / label=insufficient / score=0.9764248572687404 | Benchmark and weak-judge over-certainty under title ambiguity. |
| AUDIT-024 | Entity/title ambiguity | unfaithful | faithful | unfaithful | unfaithful | target_verdict_unreliable_strict / benchmark_reference / label=faithful / score=0.9742338091688152 | Benchmark mismatch caused by unresolved media/title ambiguity. |
| AUDIT-030 | Entity/person ambiguity | unfaithful | faithful | insufficient | unfaithful | target_verdict_unreliable_strict / benchmark_reference / label=faithful / score=0.9714556077867784 | Name ambiguity where evidence supports multiple entities. |
| AUDIT-020 | Insufficient or weakly linked evidence | unfaithful | faithful | unfaithful | unfaithful | target_verdict_unreliable_strict / benchmark_reference / label=faithful / score=0.9692182194004456 | Insufficient evidence despite superficially relevant snippets. |
| AUDIT-061 | Evidence conflict | unfaithful | unfaithful | unfaithful | unfaithful | target_verdict_high_confidence_wrong / old_weak_qwen36plus20260402 / label=insufficient / score=0.9251402684401656 | Conflict case for auditing confident automatic verdicts. |
| AUDIT-065 | Temporal/evidence conflict | unfaithful | unfaithful | unfaithful | unfaithful | target_human_unfaithful / / label= / score=1.0 | Temporal conflict case. |
| AUDIT-050 | Unsupported specificity | unfaithful | faithful | unfaithful | unfaithful | target_any_main_llm_wrong / / label= / score=0.9999852840732156 | Claim-level over-specificity under near-matching evidence. |
| AUDIT-075 | Insufficient evidence in table context | unfaithful | faithful | unfaithful | unfaithful | target_any_main_llm_wrong / / label= / score=0.9999798863642338 | Table truncation / missing-evidence case. |
| AUDIT-089 | Numeric error | unfaithful | unfaithful | unfaithful | unfaithful | target_human_unfaithful / / label= / score=1.0 | Numeric/calculation failure case. |
| AUDIT-040 | False alarm / abstention failure | faithful | faithful | faithful | unfaithful | target_verdict_high_confidence_wrong / old_weak_qwen36maxpreview / label=insufficient / score=0.955224938971624 | False-positive case for qualitative balance. |
| AUDIT-009 | False alarm / policy boundary | faithful | faithful | unfaithful | unfaithful | target_strict_en_majority_wrong / / label= / score=0.6536295798839367 | Strict-prompt false alarm. |

## Detailed Notes

### AUDIT-018: Entity/title ambiguity

- Phenomenon: A judge accepts one plausible title interpretation as certain.
- Why selected: Top-ranked unreliable verdict; human gold marks the answer unfaithful because several songs titled 'Shy Boy' appear in evidence.
- Question: Who is the artist of the song "Shy Boy"?
- Answer: The answer is Bananarama.
- Human gold: unfaithful (entity_ambiguity|over_specific_answer|benchmark_ambiguous)
- Human rationale: Several songs titled 'Shy Boy' appear in the evidence, performed by Bananarama, Secret, and Katie Melua. The answer selects Bananarama, ignoring the title ambiguity as the question did not specify a version.
- Audit signal: benchmark=faithful, old weak majority=unfaithful, strict majority=unfaithful, selected score=0.9764248572687404
- Evidence excerpt 1: [d0] Shy Boy "Shy Boy" is a song recorded by English girl group Bananarama. It appears on their 1983 debut album "Deep Sea Skiving" and was released as its second single. It was written and produced by the production team of Steve Jolley and Tony Swain and marked the first in a long line of studio collaborations between them and Bananarama. The song is rumoured to be a tribute to teenaged London pirate radio comed...
- Evidence excerpt 2: [d1] Shy Boy (Secret song) "Shy Boy" (Korean: 샤이보이) is a single by South Korean girl group Secret. It is released as a CD single on January 6, 2011 through TS Entertainment. The song was written and produced by Kang Jiwon and Kim Kibum. It was remade with Japanese lyrics and was on Secret's first Japanese EP, "Shy Boy". According to Gaon, "Shy Boy" has sold over 2,215,864 digital downloads in South Korea as of Dec...

### AUDIT-024: Entity/title ambiguity

- Phenomenon: A benchmark/reference label treats a partially supported answer as faithful despite multiple works with the same title.
- Why selected: Top unreliable benchmark/reference verdict; useful for the policy-misalignment argument.
- Question: What is the medium of "El derecho de nacer"?
- Answer: The answer is Telenovela.
- Human gold: unfaithful (entity_ambiguity|benchmark_ambiguous)
- Human rationale: The evidence includes both a 1981 television series and a 1952 film version of "El derecho de nacer," which originated from a radio novel of the same name. The answer selects the television series without addressing the media ambiguity, as the question does not specify a version.
- Audit signal: benchmark=faithful, old weak majority=unfaithful, strict majority=unfaithful, selected score=0.9742338091688152
- Evidence excerpt 1: [d0] El derecho de nacer (1981 TV series) El derecho de nacer (English title:"The right to be born") is a Mexican telenovela produced by Ernesto Alonso for Televisa in 1981. Based on the Cuban radionovela of the same name written by Félix B. Caignet adapted for TV by Fernanda Villeli and directed by Raúl Araiza. Verónica Castro and Sergio Jiménez starred as protagonists, Erika Buenfil and Humberto Zurita starred a...
- Evidence excerpt 2: [d1] El derecho de nacer (film) El derecho de nacer ("The Right to Be Born") is a Mexican film produced in 1952. It is based on a Cuban radionovela (radioplay) of the same name by Félix B. Caignet. The movie, starred by Gloria Marín, broke box office records in Mexico when it was first released María Teresa (Bárbara Gil) is a wealthy young woman who finds herself unmarried and pregnant. She approaches a doctor (Jo...

### AUDIT-030: Entity/person ambiguity

- Phenomenon: A judge chooses one person among multiple people sharing the queried name.
- Why selected: High-scoring unreliable benchmark/reference verdict; human note identifies footballer/cricketer ambiguity.
- Question: What sport is David Hancock associated with?
- Answer: The answer is Football.
- Human gold: unfaithful (entity_ambiguity|benchmark_ambiguous)
- Human rationale: The evidence lists multiple individuals named David Hancock, including a footballer and a cricketer. The answer selects football without addressing the homonym ambiguity, as the question does not specify the person.
- Audit signal: benchmark=faithful, old weak majority=insufficient, strict majority=unfaithful, selected score=0.9714556077867784
- Evidence excerpt 1: [d0] Dave Hancock (footballer) David Jeffrey Hancock (24 July 1938 – 6 June 2007) was an English professional footballer. He was born in Exeter, Devon and played for all three of the county's professional football teams as well as for the National Team, England. Hancock began his career as a junior with Plymouth Argyle, turning professional in September 1955. He played twice in the league for Argyle during the 195...
- Evidence excerpt 2: [d1] David Hancock (cricketer) David Arthur Hancock (born 28 March 1940) is a former English cricketer. Hancock was a left-handed batsman. He was born in Newcastle-under-Lyme, Staffordshire. Hancock made his debut for Staffordshire in the 1958 Minor Counties Championship against the Yorkshire Second XI. Hancock played Minor counties cricket for Staffordshire from 1958 to 1983, which included 204 Minor Counties Cha...

### AUDIT-020: Insufficient or weakly linked evidence

- Phenomenon: Evidence contains demographic facts but does not clearly link them to the queried location.
- Why selected: High-scoring unreliable benchmark/reference verdict; illustrates unsupported inference rather than simple contradiction.
- Question: What is the median age in Rushford?
- Answer: The answer is 41.9 years.
- Human gold: unfaithful (evidence_conflict|insufficient_evidence|unsupported_claim)
- Human rationale: The evidence snippets do not explicitly mention Rushford, making it unclear if the demographic data applies to this location. Additionally, the answer selects a median age of 41.9 despite conflicting values (25.7, 15.2, 40, 38) in the evidence, lacking sufficient support.
- Audit signal: benchmark=faithful, old weak majority=unfaithful, strict majority=unfaithful, selected score=0.9692182194004456
- Evidence excerpt 1: [d0] The average household size was 2.35 and the average family size was 2.93. The median age in the city was 41.9 years. 24.1% of residents were under the age of 18; 6.7% were between the ages of 18 and 24; 22.5% were from 25 to 44; 25.8% were from 45 to 64; and 21% were 65 years of age or older. The gender makeup of the city was 47.3% male and 52.7% female. As of the census of 2000, there are 1,696 people, 704 h...
- Evidence excerpt 2: [d1] living with them , 50.8 % were married couples living together , 10.9 % had a female householder with no husband present , 2.8 % had a male householder with no wife present , and 35.4 % were non-families . 30.9 % of all households were made up of individuals and 17.3 % had someone living alone who was 65 years of age or older . The average household size was 2.35 and the average family size was 2.93 . The med...

### AUDIT-061: Evidence conflict

- Phenomenon: Evidence directly conflicts about the base location of the entity.
- Why selected: Human issue categories include contradiction and evidence conflict; model confidence can still be high.
- Question: Where was Airways International based?
- Answer: The answer is Anchorage, Alaska.
- Human gold: unfaithful (contradiction|evidence_conflict)
- Human rationale: Evidence directly conflicts on the base location of Airways International, with [1] citing Miami, Florida, and [2] citing Anchorage, Alaska. The answer selects only Anchorage without addressing or resolving this conflict.
- Audit signal: benchmark=unfaithful, old weak majority=unfaithful, strict majority=unfaithful, selected score=0.9251402684401656
- Evidence excerpt 1: [d0] Airways International Airways International was an airline based in Miami, Florida. Airways international was founded in 1979 and began operations around 1984. The airline ceased operations in 1999. The carrier's primary business focus was flights within southern Florida and to the Bahamas. Airways International also operated charter flights. In 1985, Airways began service to the Bahamas with Convair 580 airc...
- Evidence excerpt 2: [d1] Airways International was an airline based in Anchorage, Alaska. Airways International was founded in 1979 and began operations around 1984. The airline ceased operations in 1999. The carrier's primary business focus was flights within southern Florida and to the Bahamas. Airways International also operated charter flights. In 1985, Airways began service to the Bahamas with Convair 580 aircraft. Throughout it...

### AUDIT-065: Temporal/evidence conflict

- Phenomenon: Evidence conflicts on when a player first represented Papua New Guinea.
- Why selected: Human note identifies conflicting dates; useful to show temporal conflict beyond entity ambiguity.
- Question: When did Morea start playing for Papua New Guinea?
- Answer: The answer is 2000.
- Human gold: unfaithful (evidence_conflict|contradiction|benchmark_ambiguous)
- Human rationale: Evidence conflicts on when player Ipi Morea first represented Papua New Guinea, with [1] stating 1996 and [3] stating 2000. The answer selects only 2000 without addressing the contradiction with [1].
- Audit signal: benchmark=unfaithful, old weak majority=unfaithful, strict majority=unfaithful, selected score=1.0
- Evidence excerpt 1: [d0] Ipi Morea Ipi Morea (born 6 May 1975) is a Papua New Guinean cricketer. A right-handed batsman and wicket-keeper, he played for the Papua New Guinea national cricket team between 1996 and 2005. Born in Port Moresby in 1975, Ipi Morea first played for Papua New Guinea in the 1996 ACC Trophy in Malaysia. This was followed the next year by an appearance in the 1997 ICC Trophy, also in Malaysia and a second ACC T...
- Evidence excerpt 2: [d1] e Asia-Pacific Economic Cooperation ( APEC ) Nations Australia Brunei Canada Chile China Hong Kong ¹ Indonesia Japan South Korea Malaysia Mexico New Zealand Papua New Guinea Peru Philippines Russia Singapore Taiwan Thailand United States Vietnam Summits 1989 1990 1991 1992 1993 1994 1995 1996 1997 1998 1999 2000 2001 2002 2003 2004 2005 2006 2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 202...

### AUDIT-050: Unsupported specificity

- Phenomenon: Answer confuses first transatlantic flight with first nonstop flight.
- Why selected: Human issue categories include unsupported claim and answer-format issue; benchmark/reference label disagrees with human gold.
- Question: When was the first transatlantic flight?
- Answer: The first non-stop transatlantic flight was made by British aviators John Alcock and Arthur Brown on June 14-15, 1919, in a modified Vickers Vimy bomber from St.
- Human gold: unfaithful (unsupported_claim|answer_format_issue)
- Human rationale: Evidence [2] and [8] show the NC-4 completed the first transatlantic flight (in stages) in May 1919. The answer instead cites Alcock and Brown's first non-stop flight in June 1919, and the text is truncated.
- Audit signal: benchmark=faithful, old weak majority=unfaithful, strict majority=unfaithful, selected score=0.9999852840732156
- Evidence excerpt 1: [d0] The first transatlantic flight by rigid airship, and the first return transatlantic flight, was made just a couple of weeks after the transatlantic flight of Alcock and Brown, on 2 July 1919. Major George Herbert Scott of the Royal Air Force flew the airship R34 with his crew and passengers from RAF East Fortune, Scotland to Mineola, New York (on Long Island), covering a distance of about in about four and a...
- Evidence excerpt 2: [d1] Transatlantic flight surpassed ocean liners as the predominant mode of crossing the Atlantic in the mid 20th century. In 1919, the American NC-4 became the first airplane to cross the Atlantic (but in multiple stages). Later that year, a British Vickers Vimy piloted by Alcock and Brown made the first non-stop transatlantic flight from Newfoundland to Ireland. Also in 1919, the British were the first to cross...

### AUDIT-075: Insufficient evidence in table context

- Phenomenon: Answer requires table values that are not visible in the truncated evidence.
- Why selected: Human issue categories include unsupported claim and insufficient evidence; shows failure on structured/table-like evidence.
- Question: What is the difference in segment operating income between Activision and Blizzard in 2017?
- Answer: The segment operating income for Activision in 2017 was $1,005 million, and for Blizzard, it was $712 million. The difference in segment operating income between Activision and Blizzard in 2017 is $293 million ($1,005 million - $712 million = $293 million).
- Human gold: unfaithful (unsupported_claim|insufficient_evidence)
- Human rationale: The provided table is truncated for the year 2017 and does not show the segment operating profits for Activision and Blizzard. The answer provides figures of $1.005 billion, $712 million, and a difference of $293 million, but these values cannot be supported by the current evidence.
- Audit signal: benchmark=faithful, old weak majority=unfaithful, strict majority=unfaithful, selected score=0.9999798863642338
- Evidence excerpt 1: [d0] Information on the reportable segment net revenues and segment operating income are presented below (amounts in millions): [["", "", "Year Ended December 31, 2019", "", ""], ["", "Activision", "Blizzard", "King", "Total"], ["Segment Revenues", "", "", "", ""], ["Net revenues from external customers", "$2,219", "$1,676", "$2,031", "$5,926"], ["Intersegment net revenues (1)", "\u2014", "43", "\u2014", "43"], ["...
- Evidence excerpt 2: [d1] (1) Intersegment revenues reflect licensing and service fees charged between segments.

### AUDIT-089: Numeric error

- Phenomenon: Answer makes an unsupported projection from operating-profit values.
- Why selected: Human issue categories include numeric error and unsupported claim; useful as a non-ambiguity failure type.
- Question: if 2014 underlying operating profit increases at the same pace as 2013 , what would it be , in millions?
- Answer: If 2014 underlying operating profit increases at the same pace as 2013, it would be $2,098 million.
- Human gold: unfaithful (numeric_error|unsupported_claim)
- Human rationale: Evidence shows base operating profits of $2,098 million in 2013 and $2,014 million in 2012; projecting similar growth yields ~$2,185.5 million for 2014, but the answer incorrectly repeats the 2013 figure instead of calculating.
- Audit signal: benchmark=unfaithful, old weak majority=unfaithful, strict majority=unfaithful, selected score=1.0
- Evidence excerpt 1: [d0] 2013 . in 2011 , asset returns were lower than expected by $ 471 million and discount rates declined resulting in an unfavorable mark-to-market adjustment recorded in earnings in the fourth quarter of 2011 . a portion of the 2011 pension mark-to- market adjustment was capitalized as an inventoriable cost at the end of 2011 . this amount was recorded in earnings in the first quarter of 2012 . mark-to-market ad...
- Evidence excerpt 2: [d1] [["( dollars in millions )", "2013", "2012", "2011"], ["reported gross profit ( a )", "$ 6103", "$ 5434", "$ 5152"], ["mark-to-market ( cogs ) ( b )", "510", "-259 ( 259 )", "-377 ( 377 )"], ["project k ( cogs ) ( c )", "-174 ( 174 )", "2014", "2014"], ["underlying gross profit ( d )", "$ 5767", "$ 5693", "$ 5529"], ["reported sga", "$ 3266", "$ 3872", "$ 3725"], ["mark-to-market ( sga ) ( b )", "437", "-193...

### AUDIT-040: False alarm / abstention failure

- Phenomenon: Human gold says the answer is faithful, but some automatic verdicts abstain or mark it unfaithful.
- Why selected: Strict majority is wrong and a high-confidence weak verdict is wrong; shows the audit layer must support review rather than automatic rejection.
- Question: What is Jon Hill's profession?
- Answer: The answer is American chef.
- Human gold: faithful ()
- Human rationale: Evidence [1]-[2] clearly identify Jon Hill as an American chef who served as Executive Chef at the White House. The answer is consistent with this evidence.
- Audit signal: benchmark=faithful, old weak majority=faithful, strict majority=unfaithful, selected score=0.955224938971624
- Evidence excerpt 1: [d0] Jon Hill (chef) Jon Hill ( 1954) is an American chef who was White House Executive Chef from October 1, 1987, to January 7, 1988. He was the first American-born chef to serve in the capacity. Hill was born in Spokane, Washington, about 1954 to Victor M. Hill, a chef and instructor of hotel-motel and restaurant management at Spokane Community College. His grandfather was also a chef. Hill fell in love with fin...
- Evidence excerpt 2: [d1] The details ( from wikipedia ) Biography Jon Hill ( c. 1954 ) is an American chef who was White House Executive Chef from October 1 , 1987 , to January 7 , 1988 . He was the first American-born chef to serve in the capacity . Early life and education Hill was born in Spokane , Washington , about 1954 to Victor M. Hill , a chef and instructor of hotel-motel and restaurant management at Spokane Community Colleg...

### AUDIT-009: False alarm / policy boundary

- Phenomenon: Human gold and benchmark/reference agree, while the strict majority is unfaithful.
- Why selected: One of only four strict-majority-wrong items; useful as a caution against overclaiming strict prompts.
- Question: current assets were what percent of net assets acquired for the can and alcan transactions?
- Answer: To calculate the percent of net assets acquired that were current assets for the U.S. Can and Alcan transactions, I need to: 1. Identify the current assets acquired in each transaction 2. Calculate the total net assets acquired for each transaction 3. Divide the current assets by the total net assets and multiply by 100 to get the percentage For the U.S. Can transaction: Current assets acquired = "other assets primarily inventories and receivables" = $218.8 million Total net assets acquired = $617.9 million Percent of net assets that were current assets = $218.8 million / $617.9 million x 100 = 35.4% For the Alcan transaction: Current assets acquired = "other assets primarily inventories and receivables" = $40.7 million Total net assets acquired = $184.7 million Percent of net assets that were current assets = $40.7 million / $184.7 million x 100 = 22.0% So the current assets were 35.4% of the net assets acquired for the U.S. Can transaction, and 22.0% of the net assets acquired for the Alcan transaction.
- Human gold: faithful ()
- Human rationale: 
- Audit signal: benchmark=faithful, old weak majority=unfaithful, strict majority=unfaithful, selected score=0.6536295798839367
- Evidence excerpt 1: [d0] page 51 of 98 notes to consolidated financial statements ball corporation and subsidiaries 3 . acquisitions ( continued ) effective january 1 , 2007 . the acquisition has been accounted for as a purchase and , accordingly , its results have been included in the consolidated financial statements since march 27 , 2006 . alcan packaging on march 28 , 2006 , ball acquired north american plastic bottle container a...
- Evidence excerpt 2: [d1] [["( $ in millions )", "u.s . can ( metal food & household products packaging americas )", "alcan ( plastic packaging americas )", "total"], ["cash", "$ 0.2", "$ 2013", "$ 0.2"], ["property plant and equipment", "165.7", "73.8", "239.5"], ["goodwill", "358.0", "53.1", "411.1"], ["intangibles", "51.9", "29.0", "80.9"], ["other assets primarily inventories and receivables", "218.8", "40.7", "259.5"], ["liabilit...
