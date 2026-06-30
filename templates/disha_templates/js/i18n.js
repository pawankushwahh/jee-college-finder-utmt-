"use strict";

/* ════════════════════════════════════════════════════════════════════════
   Disha — internationalization (i18n)

   Single source of truth for every user-facing STRING in the portal.
   - Static markup is translated via data-i18n* attributes (see applyStaticI18n).
   - Dynamic JS strings are pulled with t("dot.path", { vars }).

   Hindi (hi) uses natural, simple Devanagari and deliberately keeps technical
   terms (CSE, NIT, IIT, MBA, JEE, Target/Reach/Safe) in English where students
   expect them. Numbers are formatted by fmt() (Indian grouping) at call sites.

   Backend-generated text (guidance, notes, blurbs, fit labels, reasons) is NOT
   here — it comes from the API in the language we send via payload.lang.
   ════════════════════════════════════════════════════════════════════════ */

const LANG_KEY = "disha.lang";
const SUPPORTED_LANGS = ["en", "hi", "gu", "kn"];

const I18N = {
  en: {
    header: {
      dataNotePre: "JoSAA 2025 cutoffs · ",
      dataNotePost: " programs",
      restart: "Start over",
      langSwitchTo: "हिं",            // label of the button (switches TO Hindi)
      langSwitchAria: "Switch to Hindi",
    },
    welcome: {
      eyebrow: "For JEE Main & Advanced aspirants",
      titleHtml: "Your rank is a starting&nbsp;point, <em>not a verdict.</em>",
      ledeHtml:
        "Tell us your rank and what you want from the next four years. " +
        "We'll show you the IITs, NITs, IIITs and GFTIs where you genuinely stand a chance — " +
        "sorted into <strong class=\"tone-safe\">Safe</strong>, <strong class=\"tone-target\">Target</strong> " +
        "and <strong class=\"tone-reach\">Reach</strong> — with honest guidance for your goals.",
      cta: "Find where I stand",
      trust: "Takes about a minute · Free · Nothing is stored",
      utmtHtml:
        "An open-source initiative by <a href=\"https://www.utmt.org\" target=\"_blank\" rel=\"noopener\">UTMT</a> — learn to build AI products",
      legendSafe: "Safe", legendSafeSub: "very likely",
      legendTarget: "Target", legendTargetSub: "realistic fit",
      legendReach: "Reach", legendReachSub: "worth a try",
      offline: "We couldn't reach the recommendation service. Make sure the backend is running, then try again.",
      retry: "Retry",
    },
    flow: {
      back: "Previous question",
      continue: "Continue",
      showColleges: "Show my colleges",
      kbdHint: "press",
      s1Eyebrow: "First things first",
      s1Title: "What's your rank?",
      s1Hint: "Enter whichever ranks you have — at least one. Use your CRL (Common Rank List) rank.",
      mainsLabel: "JEE Main rank",
      mainsPlaceholder: "e.g. 12,500",
      mainsNote: "Used for NITs, IIITs and GFTIs.",
      advLabel: "JEE Advanced rank",
      optional: "optional",
      advPlaceholder: "Leave blank if you didn't appear",
      advNote: "Used for IITs.",
      s2Eyebrow: "About you",
      s2Title: "A little about you",
      s2Hint: "This decides which seat pools and quotas apply to you.",
      genderLabel: "Gender",
      categoryLabel: "Reservation category",
      s3Eyebrow: "Where you're from",
      s3Title: "Your home state",
      s3Hint: "The state where you passed Class 12. NITs reserve half their seats for home-state students, so this genuinely changes your options.",
      stateLabel: "State / Union Territory",
      statePlaceholder: "Choose your state…",
      s4Eyebrow: "The next four years",
      s4Title: "What pulls you?",
      s4Hint: "There's no wrong answer — and \u201cnot sure\u201d is a perfectly good one. We'll order branches to fit.",
      s5Eyebrow: "Branch focus",
      s5Title: "Any branch in mind?",
      s5Hint: "Pick the branch families you'd consider. Leave it on \u201cAny\u201d to keep every branch in your results.",
      s6Eyebrow: "One last look",
      s6Title: "Did we get this right?",
      s6Hint: "Tap any row to change it.",
      sIncomeEyebrow: "Financial Aid",
      sIncomeTitle: "Your family income",
      sIncomeHint: "This is used purely to estimate tuition waivers.",
      incomeLabel: "Annual Family Income",
      branchLabel: "Branch preference",
      branchAny: "Any branch",
      branchAnyDesc: "Show options across every branch",
    },
    validation: {
      ranks: "Enter at least one rank — JEE Main or Advanced — to continue.",
      state: "Pick your home state — it changes which NIT seats you can claim.",
      goal: "Pick one — \u201cNot sure yet\u201d counts.",
    },
    gender: {
      male: "Male", female: "Female", other: "Other",
      noteFemale: "Female-only (supernumerary) seats will be included for you — they often close at better ranks.",
      noteOther: "You'll be matched against gender-neutral seat pools.",
    },
    category: {
      note: "Cutoff data currently covers OPEN (CRL) seats; reserved-category cutoffs are on the way.",
      comingSoon: "coming soon",
      general: "General (OPEN)",
    },
    goals: {
      coding: { name: "Coding & software", desc: "Build things, aim for SDE roles" },
      research: { name: "Research & higher studies", desc: "MS, MTech or PhD pathways" },
      mba: { name: "MBA & management", desc: "Brand, network, placements" },
      core: { name: "Core engineering", desc: "Practice the discipline you study" },
      undecided: { name: "Not sure yet", desc: "Keep as many doors open as possible" },
    },
    goalTips: {
      coding: [
        "CSE at the top NITs often closes earlier than non-CS branches at newer IITs — compare both before ranking choices.",
        "ECE and Mathematics & Computing are close substitutes for CSE in software placements.",
        "Consistent DSA practice and internships outweigh a one-tier branch difference.",
      ],
      research: [
        "Prefer institutes with active research groups in your area — check faculty pages, not just rankings.",
        "IISc and IISERs are strong alternatives if pure science appeals to you.",
        "Start approaching professors for small projects in your first year.",
      ],
      mba: [
        "An older IIT or NIT brand carries real weight in CAT shortlists and placements.",
        "Branch choice is secondary — pick one you can score well in.",
        "Use clubs, fests and POR roles to build the profile MBA programs look for.",
      ],
      core: [
        "Older NITs frequently have stronger core-company relationships than newer IITs.",
        "PSU recruitment through GATE is a dependable core-sector pathway.",
        "Look for institutes with labs and industry tie-ups in your specific domain.",
      ],
      undecided: [
        "Most IITs allow a branch change after first year based on GPA.",
        "Broad branches (EE, Mechanical, Engineering Physics) keep many doors open.",
        "Talk to seniors in branches you're considering before locking a choice.",
      ],
    },
    quota: {
      AI: "All-India seat", HS: "Home-state quota", OS: "Other-state quota",
      GO: "Goa quota", JK: "J&K quota", LA: "Ladakh quota",
    },
    loading: [
      "Reading last year's cutoffs…",
      "Matching programs to your profile…",
      "Sorting Safe, Target and Reach…",
    ],
    error: {
      title: "That didn't work",
      generic: "Something went wrong. Please try again.",
      retry: "Try again",
      edit: "Edit my details",
    },
    review: {
      mains: "JEE Main rank", adv: "JEE Advanced rank", gender: "Gender",
      category: "Category", state: "Home state", income: "Family income", goal: "Goal", branch: "Branch",
      anyBranch: "Any branch", notGiven: "not given", dash: "—",
    },
    income: {
      below_3l: "Below ₹3 Lakh",
      "3l_5l": "₹3 Lakh - ₹5 Lakh",
      above_5l: "Above ₹5 Lakh",
      below3l: "Below ₹3 Lakh / year",
      below3lSub: "Eligible for 100% IIT/NIT tuition waiver",
      "3l5l": "Between ₹3 Lakh and ₹5 Lakh / year",
      "3l5lSub": "Eligible for 2/3rd tuition waiver at IITs and NITs",
      above5l: "Above ₹5 Lakh / year",
      above5lSub: "Standard tuition fees apply",
    },
    region: {
      all: "All India",
      metro: "Metro Cities Only",
      north: "North India",
      south: "South India",
      east: "East India",
      west: "West India",
      northeast: "Northeast / Hills",
    },
    panel: {
      toggle: "Filter / Edit",
      title: "Your inputs",
      subtitle: "Change anything — results update live.",
      mainsLabel: "JEE Main rank",
      mainsPlaceholder: "e.g. 12,500",
      incomeLabel: "Family income",
      ratioLabel: "College vs Branch Priority",
      ratioBranch: "Favour Branch",
      ratioBrand: "Favour Brand",
      regionLabel: "Geographic region",
      advLabel: "JEE Advanced rank",
      advPlaceholder: "Optional",
      genderLabel: "Gender",
      categoryLabel: "Category",
      stateLabel: "Home state",
      goalLabel: "Career goal",
      branchLabel: "Branch preference",
      updating: "Updating…",
      done: "Done",
    },
    results: {
      standingTitle: "Your standing",
      byBranch: "By branch",
      byCollege: "By college",
      edit: "Edit",
      share: "Share",
      copyLink: "Copy link",
      copied: "Copied!",
      print: "Print / Save PDF",
      noteEyebrow: "A note for you",
      noteHeadlineDefault: "Here's where you stand.",
      searchPlaceholder: "Search institute or branch…",
      searchAria: "Search results",
      typeAll: "All",
      emptyFilteredTitle: "Nothing matches those filters.",
      emptyFilteredBody: "Try clearing the search or showing all institute types.",
      clearFilters: "Clear filters",
      emptyResultsTitle: "We couldn't find close matches.",
      emptyResultsBody: "Your rank may sit far from this dataset's cutoff windows for the filters chosen. Try adding your other rank, or double-check your home state.",
      emptyEdit: "Edit my details",
      profileMain: "Main",
      profileAdvanced: "Advanced",
      disclaimerHtml:
        "Based on JoSAA 2025 Round-6 closing ranks for OPEN (CRL) seats. Cutoffs move every year — " +
        "treat this as a compass, not a contract. Verify on <strong>josaa.nic.in</strong> before locking choices. " +
        "Note: We focus on providing accurate admission insights based on official JEE cutoff data, so fee details " +
        "are not provided here. Please refer to the official websites of individual institutes for their verified fee structures.",
    },
    headlines: {
      adjust: "Let's adjust the compass.",
      good: "You're standing in a good spot.",
      options: "You have real options on the table.",
      solid: "You have solid ground to build from.",
      stretch: "It's a stretch — but not out of reach.",
    },
    zones: {
      safeName: "Safe", safeSub: "strong backups",
      targetName: "Target", targetSub: "your best-fit zone",
      reachName: "Reach", reachSub: "worth a try",
    },
    ruler: {
      introEyebrow: "The whole picture",
      lede: "Every match on one rank ruler — the dark line is you. The scale is logarithmic, so the crowded top ranks stay readable.",
      iitTitle: "IITs", iitVia: "via JEE Advanced",
      nitTitle: "NITs · IIITs · GFTIs", nitVia: "via JEE Main",
      options: "options",
      you: "You",
      yourRank: "Your rank: {rank}",
      closes: "closes",
    },
    section: {
      Target: "Target", Reach: "Reach", Safe: "Safe",
    },
    rankbar: {
      opens: "opens", closes: "closes",
      safe: "You: {rank} — ahead of last year's opening rank.",
      targetComfort: "You: {rank} — comfortably inside last year's window.",
      targetEdge: "You: {rank} — inside the window, closer to the edge.",
      reach: "You: {rank} — about {past}% past last year's closing. Cutoffs shift.",
    },
    confidence: {
      highLabel: "Stable cutoff", highHint: "Wide last-year window — unlikely to swing past you.",
      mediumLabel: "Fairly steady", mediumHint: "Last-year window is around average — moderate swing risk.",
      fragileLabel: "Volatile cutoff", fragileHint: "Very tight last-year window — the cutoff can shift sharply.",
    },
    card: {
      fitsGoal: "fits your goal",
      fitsGoalTitle: "Strong fit for your stated goal",
      dualDegree: "Dual degree (5 yr)",
      femaleSeat: "Female-only seat",
      viaAdvanced: "via JEE Advanced",
      viaMains: "via JEE Main",
      homeBadge: "Home-state: ~{n} ranks saved",
      homeBadgeTitle: "Home-state quota closes this many ranks later than the open-state seat.",
      femaleBadge: "Female seat: ~{n} ranks later",
      femaleBadgeTitle: "Female-only seat closes this many ranks later than the gender-neutral seat.",
      chance: "chance",
      probTitle: "Estimated admission probability: {prob}%",
      historyBtn: "View Cutoff History",
      historyBtnClose: "Hide Cutoff History",
    },

    footer: {
      aboutHtml: "Disha — a <a href=\"https://www.utmt.org\" target=\"_blank\" rel=\"noopener\">UTMT</a> initiative, built with care for JEE aspirants",
      openSource: "Open source · Free · No login",
      dataHtml: "Cutoff data: <a href=\"https://github.com/atmabodha/OpenNLP\" target=\"_blank\" rel=\"noopener\">OpenNLP (JoSAA 2025)</a>",
    },
    share: {
      title: "Disha — my JEE college matches",
      targetLine: "Target ({count}): {picks}",
      countsLine: "Safe {safe} · Reach {reach}",
      noTarget: "Top picks: {picks}",
      open: "Open Disha:",
      copyFail: "Couldn't copy. Long-press the address bar to copy the link.",
    },
    errors: {
      unreachable: "Could not reach the recommendation service. You may be offline — check your connection and try again.",
      requestFailed: "Request failed with status {status}.",
    },
  },

  hi: {
    header: {
      dataNotePre: "JoSAA 2025 कटऑफ़ · ",
      dataNotePost: " प्रोग्राम",
      restart: "फिर से शुरू करें",
      langSwitchTo: "EN",
      langSwitchAria: "Switch to English",
    },
    welcome: {
      eyebrow: "JEE Main और Advanced के अभ्यर्थियों के लिए",
      titleHtml: "आपकी रैंक एक शुरुआत&nbsp;है, <em>फ़ैसला नहीं।</em>",
      ledeHtml:
        "हमें अपनी रैंक बताएँ और यह भी कि अगले चार साल आप क्या चाहते हैं। " +
        "हम आपको वे IITs, NITs, IIITs और GFTIs दिखाएँगे जहाँ आपके पास सच में मौक़ा है — " +
        "<strong class=\"tone-safe\">Safe</strong>, <strong class=\"tone-target\">Target</strong> " +
        "और <strong class=\"tone-reach\">Reach</strong> में बँटे हुए — आपके लक्ष्यों के लिए ईमानदार सलाह के साथ।",
      cta: "देखें मैं कहाँ खड़ा हूँ",
      trust: "लगभग एक मिनट · मुफ़्त · कुछ भी सेव नहीं होता",
      utmtHtml:
        "<a href=\"https://www.utmt.org\" target=\"_blank\" rel=\"noopener\">UTMT</a> की एक ओपन-सोर्स पहल — AI products बनाना सीखें",
      legendSafe: "Safe", legendSafeSub: "पूरी संभावना",
      legendTarget: "Target", legendTargetSub: "उपयुक्त मेल",
      legendReach: "Reach", legendReachSub: "कोशिश लायक",
      offline: "हम recommendation सेवा तक नहीं पहुँच सके। पक्का करें कि backend चल रहा है, फिर दोबारा कोशिश करें।",
      retry: "दोबारा कोशिश करें",
    },
    flow: {
      back: "पिछला सवाल",
      continue: "आगे बढ़ें",
      showColleges: "मेरे कॉलेज दिखाएँ",
      kbdHint: "दबाएँ",
      s1Eyebrow: "सबसे पहले",
      s1Title: "आपकी रैंक क्या है?",
      s1Hint: "आपके पास जो भी रैंक है वह डालें — कम से कम एक। अपनी CRL (Common Rank List) रैंक इस्तेमाल करें।",
      mainsLabel: "JEE Main रैंक",
      mainsPlaceholder: "जैसे 12,500",
      mainsNote: "NITs, IIITs और GFTIs के लिए इस्तेमाल होती है।",
      advLabel: "JEE Advanced रैंक",
      optional: "वैकल्पिक",
      advPlaceholder: "अगर नहीं दी थी तो खाली छोड़ें",
      advNote: "IITs के लिए इस्तेमाल होती है।",
      s2Eyebrow: "आपके बारे में",
      s2Title: "थोड़ा आपके बारे में",
      s2Hint: "इससे तय होता है कि आप पर कौन-से सीट पूल और कोटा लागू होंगे।",
      genderLabel: "जेंडर",
      categoryLabel: "आरक्षण श्रेणी",
      s3Eyebrow: "आप कहाँ से हैं",
      s3Title: "आपका होम स्टेट",
      s3Hint: "वह राज्य जहाँ आपने 12वीं पास की। NITs अपनी आधी सीटें होम-स्टेट छात्रों के लिए रखती हैं, इसलिए यह सचमुच आपके विकल्प बदल देता है।",
      stateLabel: "राज्य / केंद्र शासित प्रदेश",
      statePlaceholder: "अपना राज्य चुनें…",
      s4Eyebrow: "अगले चार साल",
      s4Title: "आपको क्या खींचता है?",
      s4Hint: "कोई ग़लत जवाब नहीं है — और \u201cपक्का नहीं\u201d भी एकदम सही जवाब है। हम ब्रांच उसी हिसाब से क्रम में लगाएँगे।",
      s5Eyebrow: "ब्रांच पर ध्यान",
      s5Title: "कोई ब्रांच मन में है?",
      s5Hint: "जिन ब्रांच परिवारों पर आप विचार करेंगे उन्हें चुनें। हर ब्रांच नतीजों में रखने के लिए \u201cAny\u201d पर छोड़ दें।",
      s6Eyebrow: "एक आख़िरी नज़र",
      s6Title: "क्या यह सही है?",
      s6Hint: "बदलने के लिए किसी भी पंक्ति पर टैप करें।",
      sIncomeEyebrow: "वित्तीय सहायता",
      sIncomeTitle: "आपकी पारिवारिक आय",
      sIncomeHint: "इसका उपयोग केवल ट्यूशन फीस छूट का अनुमान लगाने के लिए किया जाता है।",
      incomeLabel: "वार्षिक पारिवारिक आय",
      branchLabel: "ब्रांच पसंद",
      branchAny: "कोई भी ब्रांच",
      branchAnyDesc: "हर ब्रांच के विकल्प दिखाएँ",
    },
    validation: {
      ranks: "आगे बढ़ने के लिए कम से कम एक रैंक डालें — JEE Main या Advanced।",
      state: "अपना होम स्टेट चुनें — इससे तय होता है कि कौन-सी NIT सीटें आप पा सकते हैं।",
      goal: "कोई एक चुनें — \u201cपक्का नहीं\u201d भी चलेगा।",
    },
    gender: {
      male: "पुरुष", female: "महिला", other: "अन्य",
      noteFemale: "आपके लिए फ़ीमेल-ओनली (supernumerary) सीटें शामिल की जाएँगी — ये अक्सर बेहतर रैंक पर बंद होती हैं।",
      noteOther: "आपका मिलान जेंडर-न्यूट्रल सीट पूल से किया जाएगा।",
    },
    category: {
      note: "कटऑफ़ डेटा अभी केवल OPEN (CRL) सीटों के लिए है; आरक्षित-श्रेणी के कटऑफ़ जल्द आ रहे हैं।",
      comingSoon: "जल्द आ रहा है",
      general: "जनरल (OPEN)",
    },
    goals: {
      coding: { name: "Coding और software", desc: "चीज़ें बनाएँ, SDE भूमिकाएँ" },
      research: { name: "Research और higher studies", desc: "MS, MTech या PhD के रास्ते" },
      mba: { name: "MBA और management", desc: "ब्रांड, network, placements" },
      core: { name: "Core engineering", desc: "अपनी पढ़ी हुई शाखा में काम करें" },
      undecided: { name: "अभी पक्का नहीं", desc: "ज़्यादा से ज़्यादा रास्ते खुले रखें" },
    },
    goalTips: {
      coding: [
        "टॉप NITs की CSE अक्सर नई IITs की non-CS ब्रांच से पहले बंद होती है — चुनाव क्रम में लगाने से पहले दोनों की तुलना करें।",
        "software placements में ECE और Mathematics & Computing, CSE के क़रीबी विकल्प हैं।",
        "लगातार DSA अभ्यास और internships, एक-tier की ब्रांच के अंतर से ज़्यादा मायने रखते हैं।",
      ],
      research: [
        "अपने क्षेत्र में सक्रिय research समूह वाले संस्थान चुनें — सिर्फ़ rankings नहीं, faculty पेज देखें।",
        "अगर शुद्ध विज्ञान पसंद है तो IISc और IISERs मज़बूत विकल्प हैं।",
        "पहले साल से ही professors से छोटे projects के लिए संपर्क करना शुरू करें।",
      ],
      mba: [
        "पुरानी IIT या NIT का ब्रांड CAT shortlists और placements में असली वज़न रखता है।",
        "ब्रांच का चुनाव गौण है — वह चुनें जिसमें आप अच्छे अंक ला सकें।",
        "clubs, fests और POR भूमिकाओं से वह profile बनाएँ जो MBA programs ढूँढते हैं।",
      ],
      core: [
        "पुरानी NITs के अक्सर नई IITs से बेहतर core-कंपनी संबंध होते हैं।",
        "GATE के ज़रिए PSU भर्ती एक भरोसेमंद core-sector रास्ता है।",
        "अपने ख़ास क्षेत्र में labs और industry साझेदारी वाले संस्थान देखें।",
      ],
      undecided: [
        "ज़्यादातर IITs पहले साल के बाद GPA के आधार पर ब्रांच बदलने देती हैं।",
        "व्यापक ब्रांच (EE, Mechanical, Engineering Physics) कई रास्ते खुले रखती हैं।",
        "ब्रांच पक्की करने से पहले उन ब्रांच के seniors से बात करें।",
      ],
    },
    quota: {
      AI: "अखिल भारतीय सीट", HS: "होम-स्टेट कोटा", OS: "अन्य-राज्य कोटा",
      GO: "गोवा कोटा", JK: "J&K कोटा", LA: "लद्दाख़ कोटा",
    },
    loading: [
      "पिछले साल के कटऑफ़ पढ़ रहे हैं…",
      "प्रोग्राम आपकी प्रोफ़ाइल से मिला रहे हैं…",
      "Safe, Target और Reach में क्रमबद्ध कर रहे हैं…",
    ],
    error: {
      title: "यह काम नहीं आया",
      generic: "कुछ ग़लत हो गया। कृपया दोबारा कोशिश करें।",
      retry: "दोबारा कोशिश करें",
      edit: "मेरी जानकारी बदलें",
    },
    review: {
      mains: "JEE Main रैंक", adv: "JEE Advanced रैंक", gender: "जेंडर",
      category: "श्रेणी", state: "होम स्टेट", income: "पारिवारिक आय", goal: "लक्ष्य", branch: "ब्रांच",
      anyBranch: "कोई भी ब्रांच", notGiven: "नहीं दी गई", dash: "—",
    },
    income: {
      below_3l: "₹3 लाख से कम",
      "3l_5l": "₹3 लाख - ₹5 लाख",
      above_5l: "₹5 लाख से अधिक",
      below3l: "₹3 लाख / वर्ष से कम",
      below3lSub: "100% IIT/NIT ट्यूशन फीस छूट के लिए पात्र",
      "3l5l": "₹3 लाख और ₹5 लाख / वर्ष के बीच",
      "3l5lSub": "IIT और NIT में 2/3 ट्यूशन फीस छूट के लिए पात्र",
      above5l: "₹5 लाख / वर्ष से अधिक",
      above5lSub: "सामान्य ट्यूशन फीस लागू",
    },
    region: {
      all: "अखिल भारतीय",
      metro: "केवल मेट्रो शहर",
      north: "उत्तर भारत",
      south: "दक्षिण भारत",
      east: "पूर्व भारत",
      west: "पश्चिम भारत",
      northeast: "पूर्वोत्तर / पर्वतीय क्षेत्र",
    },
    panel: {
      toggle: "फ़िल्टर / बदलें",
      title: "आपकी जानकारी",
      subtitle: "कुछ भी बदलें — नतीजे तुरंत अपडेट होंगे।",
      mainsLabel: "JEE Main रैंक",
      mainsPlaceholder: "जैसे 12,500",
      incomeLabel: "पारिवारिक आय",
      ratioLabel: "कॉलेज बनाम ब्रांच प्राथमिकता",
      ratioBranch: "ब्रांच प्राथमिकता",
      ratioBrand: "कॉलेज प्राथमिकता",
      regionLabel: "भौगोलिक क्षेत्र",
      advLabel: "JEE Advanced रैंक",
      advPlaceholder: "वैकल्पिक",
      genderLabel: "जेंडर",
      categoryLabel: "श्रेणी",
      stateLabel: "होम स्टेट",
      goalLabel: "करियर लक्ष्य",
      branchLabel: "ब्रांच पसंद",
      updating: "अपडेट हो रहा है…",
      done: "हो गया",
    },
    results: {
      standingTitle: "आपकी स्थिति",
      byBranch: "ब्रांच के अनुसार",
      byCollege: "कॉलेज के अनुसार",
      edit: "बदलें",
      share: "शेयर करें",
      copyLink: "लिंक कॉपी करें",
      copied: "कॉपी हो गया!",
      print: "प्रिंट / PDF सेव करें",
      noteEyebrow: "आपके लिए एक नोट",
      noteHeadlineDefault: "यहाँ आप खड़े हैं।",
      searchPlaceholder: "संस्थान या ब्रांच खोजें…",
      searchAria: "नतीजे खोजें",
      typeAll: "सभी",
      emptyFilteredTitle: "इन फ़िल्टर से कुछ मेल नहीं खाता।",
      emptyFilteredBody: "खोज हटाकर या सभी संस्थान प्रकार दिखाकर देखें।",
      clearFilters: "फ़िल्टर हटाएँ",
      emptyResultsTitle: "हमें क़रीबी मैच नहीं मिले।",
      emptyResultsBody: "चुने हुए फ़िल्टर के लिए आपकी रैंक इस डेटा के कटऑफ़ से काफ़ी दूर हो सकती है। अपनी दूसरी रैंक डालकर देखें, या होम स्टेट दोबारा जाँचें।",
      emptyEdit: "मेरी जानकारी बदलें",
      profileMain: "Main",
      profileAdvanced: "Advanced",
      disclaimerHtml:
        "OPEN (CRL) सीटों के लिए JoSAA 2025 राउंड-6 क्लोज़िंग रैंक पर आधारित। कटऑफ़ हर साल बदलते हैं — " +
        "इसे एक कम्पास मानें, अनुबंध नहीं। चुनाव लॉक करने से पहले <strong>josaa.nic.in</strong> पर जाँच लें। " +
        "नोट: हम केवल आधिकारिक JEE कटऑफ़ डेटा के आधार पर सटीक प्रवेश संभावनाओं की जानकारी देने पर ध्यान केंद्रित करते हैं, " +
        "इसलिए यहाँ शुल्क (fees) का विवरण नहीं दिया गया है। नवीनतम और सत्यापित शुल्क विवरण के लिए आप संस्थानों की आधिकारिक वेबसाइट देख सकते हैं।",
    },
    headlines: {
      adjust: "आइए कम्पास को थोड़ा ठीक करें।",
      good: "आप एक अच्छी जगह पर खड़े हैं।",
      options: "आपके पास असली विकल्प मौजूद हैं।",
      solid: "आपके पास आगे बढ़ने के लिए मज़बूत ज़मीन है।",
      stretch: "यह थोड़ा मुश्किल है — पर पहुँच से बाहर नहीं।",
    },
    zones: {
      safeName: "Safe", safeSub: "मज़बूत बैकअप",
      targetName: "Target", targetSub: "आपका सबसे उपयुक्त ज़ोन",
      reachName: "Reach", reachSub: "कोशिश लायक",
    },
    ruler: {
      introEyebrow: "पूरी तस्वीर",
      lede: "हर मैच एक ही रैंक रूलर पर — गहरी रेखा आप हैं। पैमाना logarithmic है, इसलिए भीड़ भरी ऊपरी रैंक भी पढ़ने लायक रहती हैं।",
      iitTitle: "IITs", iitVia: "JEE Advanced से",
      nitTitle: "NITs · IIITs · GFTIs", nitVia: "JEE Main से",
      options: "विकल्प",
      you: "आप",
      yourRank: "आपकी रैंक: {rank}",
      closes: "बंद होती है",
    },
    section: {
      Target: "Target", Reach: "Reach", Safe: "Safe",
    },
    rankbar: {
      opens: "खुलती", closes: "बंद होती",
      safe: "आप: {rank} — पिछले साल की ओपनिंग रैंक से आगे।",
      targetComfort: "आप: {rank} — पिछले साल की रेंज के अंदर आराम से।",
      targetEdge: "आप: {rank} — रेंज के अंदर, किनारे के क़रीब।",
      reach: "आप: {rank} — पिछले साल की क्लोज़िंग से लगभग {past}% आगे। कटऑफ़ बदलते हैं।",
    },
    confidence: {
      highLabel: "स्थिर कटऑफ़", highHint: "पिछले साल की चौड़ी रेंज — आपके पार जाने की संभावना कम।",
      mediumLabel: "काफ़ी स्थिर", mediumHint: "पिछले साल की रेंज औसत के आसपास — मध्यम बदलाव जोखिम।",
      fragileLabel: "अस्थिर कटऑफ़", fragileHint: "पिछले साल की बहुत तंग रेंज — कटऑफ़ तेज़ी से बदल सकता है।",
    },
    card: {
      fitsGoal: "आपके लक्ष्य से मेल",
      fitsGoalTitle: "आपके बताए लक्ष्य के लिए बढ़िया मेल",
      dualDegree: "डुअल डिग्री (5 वर्ष)",
      femaleSeat: "फ़ीमेल-ओनली सीट",
      viaAdvanced: "JEE Advanced से",
      viaMains: "JEE Main से",
      homeBadge: "होम-स्टेट: ~{n} रैंक की बचत",
      homeBadgeTitle: "होम-स्टेट कोटा, ओपन-स्टेट सीट से इतनी रैंक बाद बंद होता है।",
      femaleBadge: "फ़ीमेल सीट: ~{n} रैंक बाद",
      femaleBadgeTitle: "फ़ीमेल-ओनली सीट, जेंडर-न्यूट्रल सीट से इतनी रैंक बाद बंद होती है।",
      chance: "संभावना",
      probTitle: "अनुमानित प्रवेश संभावना: {prob}%",
      historyBtn: "कटऑफ़ इतिहास देखें",
      historyBtnClose: "कटऑफ़ इतिहास छुपाएं",
    },

    footer: {
      aboutHtml: "Disha — <a href=\"https://www.utmt.org\" target=\"_blank\" rel=\"noopener\">UTMT</a> की एक पहल, JEE अभ्यर्थियों के लिए सावधानी से बनाई गई",
      openSource: "ओपन सोर्स · मुफ़्त · कोई लॉगिन नहीं",
      dataHtml: "कटऑफ़ डेटा: <a href=\"https://github.com/atmabodha/OpenNLP\" target=\"_blank\" rel=\"noopener\">OpenNLP (JoSAA 2025)</a>",
    },
    share: {
      title: "Disha — मेरे JEE कॉलेज मैच",
      targetLine: "Target ({count}): {picks}",
      countsLine: "Safe {safe} · Reach {reach}",
      noTarget: "टॉप विकल्प: {picks}",
      open: "Disha खोलें:",
      copyFail: "कॉपी नहीं हो सका। लिंक कॉपी करने के लिए address bar को लॉन्ग-प्रेस करें।",
    },
    errors: {
      unreachable: "recommendation सेवा तक नहीं पहुँच सके। हो सकता है आप ऑफ़लाइन हों — अपना कनेक्शन जाँचें और दोबारा कोशिश करें।",
      requestFailed: "अनुरोध विफल रहा, status {status}।",
    },
  },
  gu: {
    header: {
      dataNotePre: "JoSAA 2025 કટઓફ · ",
      dataNotePost: " પ્રોગ્રામ્સ",
      restart: "ફરીથી શરૂ કરો",
    },
    welcome: {
      eyebrow: "JEE Main & Advanced ઉમેદવારો માટે",
      titleHtml: "તમારો રેન્ક એક શરૂઆત છે, <em>અંતિમ ચુકાદો નથી.</em>",
      ledeHtml:
        "અમને તમારો રેન્ક અને આગામી ચાર વર્ષ માટે તમારી પસંદગી જણાવો. " +
        "અમે તમને એવી IITs, NITs, IIITs અને GFTIs બતાવીશું જ્યાં તમને ખરેખર તક છે — " +
        "જેને <strong class=\"tone-safe\">Safe</strong>, <strong class=\"tone-target\">Target</strong> " +
        "અને <strong class=\"tone-reach\">Reach</strong> માં વર્ગીકૃત કરવામાં આવ્યા છે — તમારા લક્ષ્યો માટે સાચી ગાઈડન્સ સાથે.",
      cta: "મારી તક શોધો",
      trust: "આશરે એક મિનિટ લાગે છે · મફત · કંઈપણ સંગ્રહિત થતું નથી",
      utmtHtml:
        "આ એક ઓપન-સોર્સ પહેલ છે <a href=\"https://www.utmt.org\" target=\"_blank\" rel=\"noopener\">UTMT</a> દ્વારા — AI પ્રોડક્ટ્સ બનાવતા શીખો",
      legendSafe: "Safe", legendSafeSub: "ખૂબ જ સંભવિત",
      legendTarget: "Target", legendTargetSub: "વાસ્તવિક ફિટ",
      legendReach: "Reach", legendReachSub: "પ્રયત્ન કરવા જેવું",
      offline: "અમે ભલામણ સેવા સુધી પહોંચી શક્યા નથી. ખાતરી કરો કે બેકએન્ડ ચાલુ છે, પછી ફરી પ્રયાસ કરો.",
      retry: "ફરી પ્રયાસ કરો",
    },
    flow: {
      back: "પાછલો પ્રશ્ન",
      continue: "ચાલુ રાખો",
      showColleges: "મને કૉલેજો બતાવો",
      kbdHint: "દબાવો",
      s1Eyebrow: "સૌ પ્રથમ",
      s1Title: "તમારો રેન્ક શું છે?",
      s1Hint: "તમારા કોઈપણ રેન્ક દાખલ કરો — ઓછામાં ઓછો એક. તમારા CRL (કોમન રેન્ક લિસ્ટ) રેન્કનો ઉપયોગ કરો.",
      mainsLabel: "JEE Main રેન્ક",
      mainsPlaceholder: "દા.ત. 12,500",
      mainsNote: "NITs, IIITs અને GFTIs માટે વપરાય છે.",
      advLabel: "JEE Advanced રેન્ક",
      optional: "વૈકલ્પિક",
      advPlaceholder: "જો તમે પરીક્ષા ન આપી હોય તો ખાલી રાખો",
      advNote: "IITs માટે વપરાય છે.",
      s2Eyebrow: "તમારા વિશે",
      s2Title: "તમારા વિશે થોડુંક",
      s2Hint: "આનાથી નક્કી થાય છે કે કઈ સીટ પૂલ અને ક્વોટા તમને લાગુ પડે છે.",
      genderLabel: "જાતિ",
      categoryLabel: "અનામત કેટેગરી",
      s3Eyebrow: "તમે ક્યાંથી છો",
      s3Title: "તમારું હોમ સ્ટેટ",
      s3Hint: "જે રાજ્યમાંથી તમે ધોરણ 12 પાસ કર્યું છે. NITs હોમ-સ્ટેટ વિદ્યાર્થીઓ માટે અડધી સીટો અનામત રાખે છે, જેથી આ તમારી તકોને ખરેખર બદલી નાખે છે.",
      stateLabel: "રાજ્ય / કેન્દ્રશાસિત પ્રદેશ",
      statePlaceholder: "તમારું રાજ્ય પસંદ કરો…",
      s4Eyebrow: "આગામી ચાર વર્ષ",
      s4Title: "તમને શેમાં રસ છે?",
      s4Hint: "કોઈ ખોટો જવાબ નથી — અને \u201cખબર નથી\u201d એ એક સારો જવાબ છે. અમે તે મુજબ બ્રાન્ચ ઓર્ડર કરીશું.",
      s5Eyebrow: "બ્રાન્ચ ફોકસ",
      s5Title: "કોઈ ચોક્કસ બ્રાન્ચ મનમાં છે?",
      s5Hint: "તમે જે બ્રાન્ચ ધ્યાનમાં લેવા માંગો છો તે પસંદ કરો. બધી જ બ્રાન્ચ જોવા માટે તેને \u201cકોઈપણ\u201d પર રાખો.",
      s6Eyebrow: "છેલ્લી નજર",
      s6Title: "શું આ વિગતો બરાબર છે?",
      s6Hint: "બદલવા માટે કોઈપણ લાઇન પર ટેપ કરો.",
      sIncomeEyebrow: "નાણાકીય સહાય",
      sIncomeTitle: "તમારા પરિવારની આવક",
      sIncomeHint: "આનો ઉપયોગ માત્ર ટ્યુશન ફી માફીના અંદાજ માટે થાય છે.",
      incomeLabel: "વાર્ષિક કૌટુંબિક આવક",
      branchLabel: "બ્રાન્ચ પસંદગી",
      branchAny: "કોઈપણ બ્રાન્ચ",
      branchAnyDesc: "દરેક બ્રાન્ચમાં વિકલ્પો બતાવો",
    },
    validation: {
      ranks: "આગળ વધવા માટે ઓછામાં ઓછો એક રેન્ક — JEE Main અથવા Advanced — દાખલ કરો.",
      state: "તમારું હોમ સ્ટેટ પસંદ કરો — આ NIT સીટો માટે મહત્વનું છે.",
      goal: "કોઈપણ એક વિકલ્પ પસંદ કરો — \u201cખબર નથી\u201d પણ ચાલશે.",
    },
    gender: {
      male: "પુરુષ", female: "સ્ત્રી", other: "અન્ય",
      noteFemale: "સ્ત્રીઓ માટેની ખાસ (supernumerary) બેઠકો તમારા માટે શામેલ કરવામાં આવશે — તે ઘણીવાર વધુ રેન્ક પર પણ મળી જાય છે.",
      noteOther: "તમને જેન્ડર-ન્યુટ્રલ સીટ પૂલ સાથે મેચ કરવામાં આવશે.",
    },
    category: {
      note: "કટઓફ ડેટા હાલમાં OPEN (CRL) સીટોને આવરી લે છે; કેટેગરી કટઓફ ટૂંક સમયમાં ઉમેરવામાં આવશે.",
      comingSoon: "ટૂંક સમયમાં આવી રહ્યું છે",
      general: "જનરલ (OPEN)",
    },
    goals: {
      coding: { name: "કોડિંગ અને સોફ્ટવેર", desc: "પ્રોડક્ટ્સ બનાવો, SDE રોલ્સ લક્ષ્ય કરો" },
      research: { name: "રિસર્ચ અને ઉચ્ચ અભ્યાસ", desc: "MS, MTech અથવા PhD માટેના રસ્તાઓ" },
      mba: { name: "MBA અને મેનેજમેન્ટ", desc: "બ્રાન્ડ, નેટવર્ક, પ્લેસમેન્ટ્સ" },
      core: { name: "કોર એન્જિનિયરિંગ", desc: "તમે જે વિષય ભણો છો તેની પ્રેક્ટિસ કરો" },
      undecided: { name: "હજી નક્કી નથી", desc: "બને તેટલા દરવાજા ખુલ્લા રાખો" },
    },
    goalTips: {
      coding: [
        "ટોચની NITs માં CSE બ્રાન્ચ ઘણીવાર નવી IITs ની બિન-CS બ્રાન્ચ કરતાં વહેલી બંધ થાય છે — બંનેની સરખામણી કરો.",
        "ECE અને મેથેમેટિક્સ એન્ડ કોમ્પ્યુટિંગ સોફ્ટવેર પ્લેસમેન્ટ માટે CSE ની નજીકના વિકલ્પો છે.",
        "સતત DSA પ્રેક્ટિસ અને ઇન્ટર્નશિપ કૉલેજ બ્રાન્ડ કરતાં વધુ મહત્વપૂર્ણ છે.",
      ],
      research: [
        "તમારા ક્ષેત્રમાં સક્રિય સંશોધન જૂથો ધરાવતી કૉલેજો પસંદ કરો — માત્ર રેન્કિંગ નહીં, ફેકલ્ટી પેજ પણ જુઓ.",
        "જો તમને શુદ્ધ વિજ્ઞાન ગમતું હોય તો IISc અને IISERs મજબૂત વિકલ્પો છે.",
        "તમારા પ્રથમ વર્ષમાં જ પ્રોફેસરો સાથે નાના પ્રોજેક્ટ્સ માટે વાત કરવાનું શરૂ કરો.",
      ],
      mba: [
        "જૂની IIT અથવા NIT ની બ્રાન્ડ MBA શોર્ટલિસ્ટ અને પ્લેસમેન્ટમાં ઘણું મહત્વ ધરાવે છે.",
        "બ્રાન્ચની પસંદગી ગૌણ છે — એવી બ્રાન્ચ પસંદ કરો જેમાં તમે સારો સ્કોર લાવી શકો.",
        "MBA પ્રોગ્રામ્સ જે પ્રોફાઇલ શોધે છે તે બનાવવા માટે ક્લબ્સ અને ફેસ્ટ્સમાં ભાગ લો.",
      ],
      core: [
        "નવી IITs કરતાં જૂની NITs માં કોર-કંપનીઓ સાથે વધુ સારા સંબંધો હોય છે.",
        "GATE પરીક્ષા દ્વારા PSU માં ભરતી એ કોર સેક્ટરનો એક મજબૂત માર્ગ છે.",
        "તમારા ચોક્કસ ક્ષેત્રમાં સારી લેબ્સ અને ઇન્ડસ્ટ્રી કનેક્શન ધરાવતી સંસ્થાઓ શોધો.",
      ],
      undecided: [
        "મોટાભાગની IITs માં પ્રથમ વર્ષ પછી GPA ના આધારે બ્રાન્ચ બદલવાની મંજૂરી હોય છે.",
        "બહોળી બ્રાન્ચો (EE, મિકેનિકલ, એન્જિનિયરિંગ ફિઝિક્સ) ભવિષ્ય માટે ઘણા વિકલ્પો ખુલ્લા રાખે છે.",
        "તમારી પસંદગીઓ નક્કી કરતા પહેલાં સિનિયર્સ સાથે ચોક્કસ વાત કરો.",
      ],
    },
    quota: {
      AI: "ઓલ ઇન્ડિયા સીટ", HS: "હોમ-સ્ટેટ ક્વોટા", OS: "અધર-સ્ટેટ ક્વોટા",
      GO: "ગોવા ક્વોટા", JK: "જે એન્ડ કે ક્વોટા", LA: "લદ્દાખ ક્વોટા",
    },
    loading: [
      "ગયા વર્ષના કટઓફ વાંચી રહ્યા છીએ…",
      "તમારી પ્રોફાઇલ સાથે મેળ ખાતા પ્રોગ્રામ્સ શોધી રહ્યા છીએ…",
      "Safe, Target અને Reach સૉર્ટ કરી રહ્યા છીએ…",
    ],
    error: {
      title: "કંઈક ખોટું થયું",
      generic: "કંઈક ભૂલ થઈ છે. કૃપા કરીને ફરી પ્રયાસ કરો.",
      retry: "ફરી પ્રયાસ કરો",
      edit: "મારી વિગતો સુધારો",
    },
    review: {
      mains: "JEE Main રેન્ક", adv: "JEE Advanced રેન્ક", gender: "જાતિ",
      category: "કેટેગરી", state: "હોમ સ્ટેટ", income: "કૌટુંબિક આવક", goal: "લક્ષ્ય", branch: "બ્રાન્ચ",
      anyBranch: "કોઈપણ બ્રાન્ચ", notGiven: "આપેલ નથી", dash: "—",
    },
    income: {
      below_3l: "₹3 લાખથી ઓછી",
      "3l_5l": "₹3 લાખ - ₹5 લાખ",
      above_5l: "₹5 લાખથી વધુ",
      below3l: "₹3 લાખ/વર્ષથી ઓછી",
      below3lSub: "100% IIT/NIT ટ્યુશન ફી માફી માટે પાત્ર",
      "3l5l": "₹3 લાખ અને ₹5 લાખ/વર્ષ વચ્ચે",
      "3l5lSub": "IITs અને NITs માં 2/3 ટ્યુશન ફી માફી માટે પાત્ર",
      above5l: "₹5 લાખ/વર્ષથી વધુ",
      above5lSub: "સામાન્ય ટ્યુશન ફી લાગુ પડશે",
    },
    region: {
      all: "ઓલ ઇન્ડિયા",
      metro: "માત્ર મેટ્રો શહેરો",
      north: "ઉત્તર ભારત",
      south: "દક્ષિણ ભારત",
      east: "પૂર્વ ભારત",
      west: "પશ્ચિમ ભારત",
      northeast: "ઉત્તરપૂર્વ / પર્વતીય",
    },
    panel: {
      toggle: "ફિલ્ટર / સુધારો",
      title: "તમારી વિગતો",
      subtitle: "કંઈપણ બદલો — પરિણામો તરત અપડેટ થશે.",
      mainsLabel: "JEE Main રેન્ક",
      mainsPlaceholder: "દા.ત. 12,500",
      incomeLabel: "કૌટુંબિક આવક",
      ratioLabel: "કૉલેજ વિ બ્રાન્ચ પ્રાધાન્યતા",
      ratioBranch: "બ્રાન્ચ તરફ ઝુકાવ",
      ratioBrand: "કૉલેજ બ્રાન્ડ તરફ ઝુકાવ",
      regionLabel: "ભૌગોલિક પ્રદેશ",
      advLabel: "JEE Advanced રેન્ક",
      advPlaceholder: "વૈકલ્પિક",
      genderLabel: "જાતિ",
      categoryLabel: "કેટેગરી",
      stateLabel: "હોમ સ્ટેટ",
      goalLabel: "કરિયર લક્ષ્ય",
      branchLabel: "બ્રાન્ચ પસંદગી",
      updating: "અપડેટ થઈ રહ્યું છે…",
      done: "થઈ ગયું",
    },
    results: {
      standingTitle: "તમારું સ્થાન",
      byBranch: "બ્રાન્ચ મુજબ",
      byCollege: "કૉલેજ મુજબ",
      edit: "સુધારો",
      share: "શેર કરો",
      copyLink: "લિંક કોપી કરો",
      copied: "કોપી થઈ ગયું!",
      print: "પ્રિન્ટ / PDF સેવ કરો",
      noteEyebrow: "તમારા માટે એક નોંધ",
      noteHeadlineDefault: "તમારી સ્થિતિ અહીં છે.",
      searchPlaceholder: "કૉલેજ અથવા બ્રાન્ચ શોધો…",
      searchAria: "શોધ પરિણામો",
      typeAll: "બધા",
      emptyFilteredTitle: "આ ફિલ્ટર્સ સાથે કંઈ મેચ થતું નથી.",
      emptyFilteredBody: "સર્ચ સાફ કરવાનો પ્રયાસ કરો અથવા બધી સંસ્થાઓ બતાવો.",
      clearFilters: "ફિલ્ટર સાફ કરો",
      emptyResultsTitle: "અમને કોઈ નજીકના મેળ મળ્યા નથી.",
      emptyResultsBody: "તમારો રેન્ક પસંદ કરેલા ફિલ્ટર્સ માટે આ ડેટાસેટના કટઓફ કરતા ઘણો દૂર હોઈ શકે છે. તમારો બીજો રેન્ક ઉમેરવાનો પ્રયાસ કરો અથવા તમારું હોમ સ્ટેટ તપાસો.",
      emptyEdit: "મારી વિગતો સુધારો",
      profileMain: "Main",
      profileAdvanced: "Advanced",
      disclaimerHtml:
        "OPEN (CRL) સીટો માટે JoSAA 2025 રાઉન્ડ-6 ના કટઓફ પર આધારિત. કટઓફ દર વર્ષે બદલાય છે — " +
        "આને દિશા સૂચક માનો, કરાર નહીં. પસંદગી લોક કરતા પહેલાં <strong>josaa.nic.in</strong> પર ખાતરી કરો. " +
        "નોંધ: અમે સત્તાવાર JEE કટઓફ ડેટા પર આધારિત સચોટ માહિતી આપવા પર ધ્યાન કેન્દ્રિત કરીએ છીએ, તેથી અહીં ફી વિગતો શામેલ નથી. સત્તાવાર ફી વિગતો માટે સંસ્થાઓની વેબસાઇટ જુઓ.",
    },
    headlines: {
      adjust: "ચાલો વિગતો થોડી ગોઠવીએ.",
      good: "તમે સારી સ્થિતિમાં છો.",
      options: "તમારી પાસે સારા વિકલ્પો ઉપલબ્ધ છે.",
      solid: "તમારી પાસે આગળ વધવા માટે મજબૂત પાયો છે.",
      stretch: "થોડું મુશ્કેલ છે — પણ અશક્ય નથી.",
    },
    zones: {
      safeName: "Safe", safeSub: "મજબૂત બેકઅપ",
      targetName: "Target", targetSub: "તમારો શ્રેષ્ઠ-ફિટ ઝોન",
      reachName: "Reach", reachSub: "પ્રયત્ન કરવા જેવું",
    },
    ruler: {
      introEyebrow: "આખી ચિત્ર",
      lede: "એક જ સ્કેલ પર તમામ પરિણામો — ડાર્ક લાઇન તમે છો. સ્કેલ logarithmic છે, જેથી ગીચ ટોચના રેન્ક પણ વાંચી શકાય.",
      iitTitle: "IITs", iitVia: "JEE Advanced દ્વારા",
      nitTitle: "NITs · IIITs · GFTIs", nitVia: "JEE Main દ્વારા",
      options: "વિકલ્પો",
      you: "તમે",
      yourRank: "તમારો રેન્ક: {rank}",
      closes: "બંધ થાય છે",
    },
    section: {
      Target: "Target", Reach: "Reach", Safe: "Safe",
    },
    rankbar: {
      opens: "ખુલે છે", closes: "બંધ થાય છે",
      safe: "તમે: {rank} — ગયા વર્ષના ઓપનિંગ રેન્ક કરતાં આગળ.",
      targetComfort: "તમે: {rank} — ગયા વર્ષની રેન્જની વચ્ચે.",
      targetEdge: "તમે: {rank} — રેન્જની અંદર, પણ કિનારીની નજીક.",
      reach: "તમે: {rank} — ગયા વર્ષના ક્લોઝિંગ કરતાં આશરે {past}% પાછળ. કટઓફ બદલાય છે.",
    },
    confidence: {
      highLabel: "સ્થિર કટઓફ", highHint: "ગયા વર્ષની પહોળી રેન્જ — તમારા કટઓફથી વહેલા બદલાવાની શક્યતા ઓછી છે.",
      mediumLabel: "સાધારણ સ્થિર", mediumHint: "ગયા વર્ષની રેન્જ સરેરાશ હતી — મધ્યમ ફેરફારનું જોખમ.",
      fragileLabel: "અસ્થિર કટઓફ", fragileHint: "ગયા વર્ષની ખૂબ જ સાંકડી રેન્જ — કટઓફ ઝડપથી બદલાઈ શકે છે.",
    },
    card: {
      fitsGoal: "લક્ષ્ય સાથે સુસંગત",
      fitsGoalTitle: "તમારા જણાવેલા લક્ષ્ય માટે યોગ્ય મેળ",
      dualDegree: "ડ્યુઅલ ડિગ્રી (5 વર્ષ)",
      femaleSeat: "માત્ર સ્ત્રીઓ માટેની બેઠક",
      viaAdvanced: "JEE Advanced દ્વારા",
      viaMains: "JEE Main દ્વારા",
      homeBadge: "હોમ-સ્ટેટ: ~{n} રેન્કનો ફાયદો",
      homeBadgeTitle: "હોમ-સ્ટેટ ક્વોટા ઓપન-સ્ટેટ સીટ કરતાં આટલા રેન્ક મોડો બંધ થાય છે.",
      femaleBadge: "સ્ત્રી સીટ: ~{n} રેન્ક બાદ",
      femaleBadgeTitle: "સ્ત્રીઓ માટેની સીટ જેન્ડર-ન્યુટ્રલ સીટ કરતાં આટલા રેન્ક મોડી બંધ થાય છે.",
      chance: "તક",
      probTitle: "અંદાજિત પ્રવેશ શક્યતા: {prob}%",
      historyBtn: "કટઓફ ઇતિહાસ જુઓ",
      historyBtnClose: "કટઓફ ઇતિહાસ છુપાવો",
    },
    footer: {
      aboutHtml: "Disha — <a href=\"https://www.utmt.org\" target=\"_blank\" rel=\"noopener\">UTMT</a> ની પહેલ, JEE ઉમેદવારો માટે ખાસ બનાવેલ",
      openSource: "ઓપન સોર્સ · મફત · કોઈ લોગિન નહીં",
      dataHtml: "કટઓફ ડેટા: <a href=\"https://github.com/atmabodha/OpenNLP\" target=\"_blank\" rel=\"noopener\">OpenNLP (JoSAA 2025)</a>",
    },
    share: {
      title: "Disha — મારા JEE કૉલેજ મેચ",
      targetLine: "Target ({count}): {picks}",
      countsLine: "Safe {safe} · Reach {reach}",
      noTarget: "ટોચની કૉલેજો: {picks}",
      open: "Disha ખોલો:",
      copyFail: "કોપી થઈ શક્યું નથી. એડ્રેસ બાર પરથી લિંક કોપી કરો.",
    },
    errors: {
      unreachable: "ભલામણ સેવા સુધી પહોંચી શકાયું નથી. તમે ઓફલાઇન હોઈ શકો છો — જોડાણ તપાસો અને ફરી પ્રયાસ કરો.",
      requestFailed: "status {status} સાથે વિનંતી નિષ્ફળ ગઈ.",
    },
  },
  kn: {
    header: {
      dataNotePre: "JoSAA 2025 ಕಟ್‌ಆಫ್ · ",
      dataNotePost: " ಕೋರ್ಸ್‌ಗಳು",
      restart: "ಮತ್ತೆ ಪ್ರಾರಂಭಿಸಿ",
    },
    welcome: {
      eyebrow: "JEE Main & Advanced ಆಕಾಂಕ್ಷಿಗಳಿಗೆ",
      titleHtml: "ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಕೇವಲ ಒಂದು ಆರಂಭ, <em>ಅಂತಿಮ ತೀರ್ಪಲ್ಲ.</em>",
      ledeHtml:
        "ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಮತ್ತು ಮುಂದಿನಹಾಲು ವರ್ಷಗಳ ನಿಮ್ಮ ಆಸಕ್ತಿಯನ್ನು ತಿಳಿಸಿ. " +
        "ನಿಮಗೆ ನಿಜವಾಗಿಯೂ ಅವಕಾಶವಿರುವ IITs, NITs, IIITs ಮತ್ತು GFTIs ಗಳನ್ನು ನಾವು ತೋರಿಸುತ್ತೇವೆ — " +
        "ಅವುಗಳನ್ನು <strong class=\"tone-safe\">Safe</strong>, <strong class=\"tone-target\">Target</strong> " +
        "ಮತ್ತು <strong class=\"tone-reach\">Reach</strong> ಎಂದು ವಿಂಗಡಿಸಲಾಗಿದೆ — ನಿಮ್ಮ ಗುರಿಗಳಿಗೆ ಪ್ರಾಮಾಣಿಕ ಮಾರ್ಗದರ್ಶನದೊಂದಿಗೆ.",
      cta: "ನನ್ನ ಅವಕಾಶಗಳನ್ನು ಹುಡುಕಿ",
      trust: "ಸುಮಾರು ಒಂದು ನಿಮಿಷ ತಗಲುತ್ತದೆ · ಉಚಿತ · ಯಾವುದೇ ಮಾಹಿತಿ ಉಳಿಯುವುದಿಲ್ಲ",
      utmtHtml:
        "<a href=\"https://www.utmt.org\" target=\"_blank\" rel=\"noopener\">UTMT</a> ನ ಮುಕ್ತ ಆಕರ ಉಪಕ್ರಮ — AI ಉತ್ಪನ್ನಗಳನ್ನು ನಿರ್ಮಿಸಲು ಕಲಿಯಿರಿ",
      legendSafe: "Safe", legendSafeSub: "ಬಹಳಷ್ಟು ಸಾಧ್ಯತೆ",
      legendTarget: "Target", legendTargetSub: "ಸೂಕ್ತ ಹೊಂದಾಣಿಕೆ",
      legendReach: "Reach", legendReachSub: "ಪ್ರಯತ್ನಿಸಬಹುದಾದ",
      offline: "ಶಿಫಾರಸು ಸೇವೆಯನ್ನು ಸಂಪರ್ಕಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ಬ್ಯಾಕೆಂಡ್ ರನ್ ಆಗುತ್ತಿದೆಯೇ ಎಂದು ಖಚಿತಪಡಿಸಿಕೊಂಡು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
      retry: "ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ",
    },
    flow: {
      back: "ಹಿಂದಿನ ಪ್ರಶ್ನೆ",
      continue: "ಮುಂದುವರಿಯಿರಿ",
      showColleges: "ನನ್ನ ಕಾಲೇಜುಗಳನ್ನು ತೋರಿಸಿ",
      kbdHint: "ಒತ್ತಿ",
      s1Eyebrow: "ಮೊದಲನೆಯದಾಗಿ",
      s1Title: "ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಎಷ್ಟು?",
      s1Hint: "ನಿಮ್ಮ ಯಾವುದೇ ರ‍್ಯಾಂಕ್‌ಗಳನ್ನು ನಮೂದಿಸಿ — ಕನಿಷ್ಠ ಒಂದು. ನಿಮ್ಮ CRL (ಕಾಮನ್ ರ‍್ಯಾಂಕ್ ಲಿಸ್ಟ್) ರ‍್ಯಾಂಕ್ ಬಳಸಿ.",
      mainsLabel: "JEE Main ರ‍್ಯಾಂಕ್",
      mainsPlaceholder: "ಉದಾ: 12,500",
      mainsNote: "NITs, IIITs ಮತ್ತು GFTIs ಗೆ ಬಳಸಲಾಗುತ್ತದೆ.",
      advLabel: "JEE Advanced ರ‍್ಯಾಂಕ್",
      optional: "ಐಚ್ಛಿಕ",
      advPlaceholder: "ಪರೀಕ್ಷೆಗೆ ಹಾಜರಾಗದಿದ್ದರೆ ಖಾಲಿ ಬಿಡಿ",
      advNote: "IITs ಗೆ ಬಳಸಲಾಗುತ್ತದೆ.",
      s2Eyebrow: "ನಿಮ್ಮ ಬಗ್ಗೆ",
      s2Title: "ನಿಮ್ಮ ಬಗ್ಗೆ ಸ್ವಲ್ಪ ತಿಳಿಸಿ",
      s2Hint: "ಇದು ನಿಮಗೆ ಅನ್ವಯವಾಗುವ ಸೀಟುಗಳ ವರ್ಗ ಮತ್ತು ಕೋಟಾಗಳನ್ನು ನಿರ್ಧರಿಸುತ್ತದೆ.",
      genderLabel: "ಲಿಂಗ",
      categoryLabel: "ಮೀಸಲಾತಿ ವರ್ಗ",
      s3Eyebrow: "ನಿಮ್ಮ ಸ್ಥಳ",
      s3Title: "ನಿಮ್ಮ ತವರು ರಾಜ್ಯ",
      s3Hint: "ನೀವು 12 ನೇ ತರಗತಿ ತೇರ್ಗಡೆಯಾದ ರಾಜ್ಯ. NITs ಅರ್ಧದಷ್ಟು ಸೀಟುಗಳನ್ನು ತವರು ರಾಜ್ಯದ ವಿದ್ಯಾರ್ಥಿಗಳಿಗೆ ಕಾಯ್ದಿರಿಸುತ್ತವೆ, ಆದ್ದರಿಂದ ಇದು ನಿಮ್ಮ ಅವಕಾಶಗಳನ್ನು ಧನಾತ್ಮಕವಾಗಿ ಬದಲಾಯಿಸುತ್ತದೆ.",
      stateLabel: "ರಾಜ್ಯ / ಕೇಂದ್ರಾಡಳಿತ ಪ್ರದೇಶ",
      statePlaceholder: "ನಿಮ್ಮ ರಾಜ್ಯವನ್ನು ಆರಿಸಿ…",
      s4Eyebrow: "ಮುಂದಿನ ನಾಲ್ಕು ವರ್ಷಗಳು",
      s4Title: "ನಿಮ್ಮ ಆಸಕ್ತಿ ಏನು?",
      s4Hint: "ಯಾವುದೇ ತಪ್ಪು ಉತ್ತರವಿಲ್ಲ — ಮತ್ತು \u201cಗೊತ್ತಿಲ್ಲ\u201d ಎಂಬುದು ಉತ್ತಮ ಉತ್ತರವಾಗಿದೆ. ಆಸಕ್ತಿಗೆ ತಕ್ಕಂತೆ ನಾವು ಬ್ರಾಂಚ್‌ಗಳನ್ನು ಜೋಡಿಸುತ್ತೇವೆ.",
      s5Eyebrow: "ಬ್ರಾಂಚ್ ಫೋಕಸ್",
      s5Title: "ಯಾವುದಾದರೂ ನಿರ್ದಿಷ್ಟ ಬ್ರಾಂಚ್ ಇದೆಯೇ?",
      s5Hint: "ನೀವು ಪರಿಗಣಿಸಲು ಬಯಸುವ ಬ್ರಾಂಚ್‌ಗಳನ್ನು ಆರಿಸಿ. ಎಲ್ಲಾ ಬ್ರಾಂಚ್‌ಗಳನ್ನು ನೋಡಲು ಇದನ್ನು \u201cಯಾವುದಾದರೂ\u201d ಆಯ್ಕೆಯಲ್ಲೇ ಬಿಡಿ.",
      s6Eyebrow: "ಕೊನೆಯ ನೋಟ",
      s6Title: "ಈ ವಿವರಗಳು ಸರಿಯಾಗಿವೆಯೇ?",
      s6Hint: "ಬದಲಾಯಿಸಲು ಯಾವುದೇ ಸಾಲಿನ ಮೇಲೆ ಟ್ಯಾಪ್ ಮಾಡಿ.",
      sIncomeEyebrow: "ಹಣಕಾಸು ನೆರವು",
      sIncomeTitle: "ನಿಮ್ಮ ಕುಟುಂಬದ ಆದಾಯ",
      sIncomeHint: "ಇದನ್ನು ಬೋಧನಾ ಶುಲ್ಕ ರಿಯಾಯಿತಿಗಳನ್ನು ಅಂದಾಜು ಮಾಡಲು ಮಾತ್ರ ಬಳಸಲಾಗುತ್ತದೆ.",
      incomeLabel: "ಕುಟುಂಬದ ವಾರ್ಷಿಕ ಆದಾಯ",
      branchLabel: "ಬ್ರಾಂಚ್ ಆದ್ಯತೆ",
      branchAny: "ಯಾವುದಾದರೂ ಬ್ರಾಂಚ್",
      branchAnyDesc: "ಎಲ್ಲಾ ಬ್ರಾಂಚ್‌ಗಳಲ್ಲೂ ಇರುವ ಆಯ್ಕೆಗಳನ್ನು ತೋರಿಸಿ",
    },
    validation: {
      ranks: "ಮುಂದುವರಿಯಲು ಕನಿಷ್ಠ ಒಂದು ರ‍್ಯಾಂಕ್ — JEE Main ಅಥವಾ Advanced — ನಮೂದಿಸಿ.",
      state: "ನಿಮ್ಮ ತವರು ರಾಜ್ಯವನ್ನು ಆರಿಸಿ — ಇದು NIT ಸೀಟುಗಳಿಗೆ ಮುಖ್ಯವಾಗಿದೆ.",
      goal: "ಯಾವುದಾದರೂ ಒಂದು ಆಯ್ಕೆಯನ್ನು ಆರಿಸಿ — \u201cಖಚಿತವಾಗಿ ಗೊತ್ತಿಲ್ಲ\u201d ಕೂಡ ಓಕೆ.",
    },
    gender: {
      male: "ಪುರುಷ", female: "ಮಹಿಳೆ", other: "ಇತರ",
      noteFemale: "ಮಹಿಳಾ ಮೀಸಲು (supernumerary) ಸೀಟುಗಳನ್ನು ನಿಮಗಾಗಿ ಪರಿಗಣಿಸಲಾಗುವುದು — ಇವು ಸಾಮಾನ್ಯವಾಗಿ ಹೆಚ್ಚಿನ ರ‍್ಯಾಂಕ್‌ಗಳಲ್ಲೂ ದೊರೆಯುತ್ತವೆ.",
      noteOther: "ನಿಮ್ಮನ್ನು ಜೆಂಡರ್-ನ್ಯೂಟ್ರಲ್ ಸೀಟುಗಳಿಗೆ ಮ್ಯಾಚ್ ಮಾಡಲಾಗುತ್ತದೆ.",
    },
    category: {
      note: "ಕಟ್‌ಆಫ್ ಡೇಟಾ ಸದ್ಯಕ್ಕೆ OPEN (CRL) ಸೀಟುಗಳನ್ನು ಮಾತ್ರ ಒಳಗೊಂಡಿದೆ; ಮೀಸಲಾತಿ ವರ್ಗದ ಕಟ್‌ಆಫ್ ಶೀಘ್ರದಲ್ಲೇ ಬರಲಿದೆ.",
      comingSoon: "ಶೀಘ್ರದಲ್ಲೇ ಬರಲಿದೆ",
      general: "ಜನರಲ್ (OPEN)",
    },
    goals: {
      coding: { name: "ಕೋಡಿಂಗ್ ಮತ್ತು ಸಾಫ್ಟ್‌ವೇರ್", desc: "ನಿರ್ಮಾಣ ಮಾಡಿ, SDE ಪಾತ್ರಗಳನ್ನು ಗುರಿಯಾಗಿಸಿ" },
      research: { name: "ಸಂಶೋಧನೆ ಮತ್ತು ಉನ್ನತ ವ್ಯಾಸಂಗ", desc: "MS, MTech ಅಥವಾ PhD ಮಾರ್ಗಗಳು" },
      mba: { name: "MBA ಮತ್ತು ನಿರ್ವಹಣೆ", desc: "ಬ್ರಾಂಡ್, ನೆಟ್‌ವರ್ಕ್, ಪ್ಲೇಸ್‌ಮೆಂಟ್ಸ್" },
      core: { name: "ಕೋರ್ ಇಂಜಿನಿಯರಿಂಗ್", desc: "ನೀವು ಓದುವ ವಿಷಯದಲ್ಲೇ ವೃತ್ತಿಪರರಾಗಿ" },
      undecided: { name: "ಇನ್ನೂ ನಿರ್ಧರಿಸಿಲ್ಲ", desc: "ಹೆಚ್ಚಿನ ಆಯ್ಕೆಗಳನ್ನು ತೆರೆದಿಡಿ" },
    },
    goalTips: {
      coding: [
        "ಉನ್ನತ NITs ಗಳ CSE ಬ್ರಾಂಚ್ ಸಾಮಾನ್ಯವಾಗಿ ಹೊಸ IITs ಗಳ ಬ್ರಾಂಚ್‌ಗಳಿಗಿಂತ ಮುಂಚಿತವಾಗಿ ಕ್ಲೋಸ್ ಆಗುತ್ತದೆ — ಎರಡನ್ನೂ ಹೋಲಿಸಿ ನೋಡಿ.",
        "ECE ಮತ್ತು ಮ್ಯಾಥಮೆಟಿಕ್ಸ್ & ಕಂಪ್ಯೂಟಿಂಗ್ ಸಾಫ್ಟ್‌ವೇರ್ ಕ್ಷೇತ್ರಕ್ಕೆ CSE ಗೆ ಉತ್ತಮ ಪರ್ಯಾಯಗಳಾಗಿವೆ.",
        "ಕಾಲೇಜು ಬ್ರಾಂಡ್ ಗಿಂತಲೂ ನಿರಂತರ DSA ಅಭ್ಯಾಸ ಮತ್ತು ಇಂಟರ್ನ್‌ಶಿಪ್‌ಗಳು ಪ್ರಮುಖ ಪಾತ್ರ ವಹಿಸುತ್ತವೆ.",
      ],
      research: [
        "ನಿಮ್ಮ ಆಸಕ್ತಿಯ ಕ್ಷೇತ್ರದಲ್ಲಿ ಸಕ್ರಿಯ ಸಂಶೋಧನಾ ತಂಡಗಳನ್ನು ಹೊಂದಿರುವ ಕಾಲೇಜುಗಳನ್ನು ಆಯ್ಕೆ ಮಾಡಿ — ಬರೀ ರ‍್ಯಾಂಕಿಂಗ್ ಅಲ್ಲದೆ ಪ್ರೊಫೆಸರ್‌ಗಳ ಪ್ರೊಫೈಲ್ ಗಮನಿಸಿ.",
        "ಶುದ್ಧ ವಿಜ್ಞಾನದಲ್ಲಿ ಆಸಕ್ತಿ ಇದ್ದರೆ IISc and IISERs ಉತ್ತಮ ಪರ್ಯಾಯಗಳಾಗಿವೆ.",
        "ನಿಮ್ಮ ಮೊದಲ ವರ್ಷದಲ್ಲೇ ಪ್ರೊಫೆಸರ್‌ಗಳೊಂದಿಗೆ ಸಣ್ಣ ಸಂಶೋಧನಾ ಯೋಜನೆಗಳಿಗೆ ಸಂಪರ್ಕಿಸಿ.",
      ],
      mba: [
        "ಹಳೆಯ IIT ಅಥವಾ NIT ಬ್ರಾಂಡ್ ಮೌಲ್ಯವು MBA ಶಾರ್ಟ್‌ಲಿಸ್ಟ್‌ಗಳು ಮತ್ತು ಉದ್ಯೋಗಾವಕಾಶಗಳಲ್ಲಿ ಬಹಳ ಸಹಕಾರಿಯಾಗಿದೆ.",
        "ಬ್ರಾಂಚ್ ಮುಖ್ಯವಲ್ಲ — ಹೆಚ್ಚು ಅಂಕ ಗಳಿಸಬಹುದಾದ ಬ್ರಾಂಚ್ ಆರಿಸಿ.",
        "MBA ಪ್ರೋಗ್ರಾಂಗಳು ಬಯಸುವ ನಾಯಕತ್ವದ ಪ್ರೊಫೈಲ್ ಬೆಳೆಸಲು ಕ್ಲಬ್ ಮತ್ತು ಉತ್ಸವಗಳಲ್ಲಿ ಸಕ್ರಿಯವಾಗಿ ಪಾಲ್ಗೊಳ್ಳಿ.",
      ],
      core: [
        "ಹೊಸ IITs ಗಿಂತ ಹಳೆಯ NITs ಗಳು ಕೋರ್ ಕಂಪನಿಗಳೊಂದಿಗೆ ಬಲವಾದ ಸಂಪರ್ಕವನ್ನು ಹೊಂದಿವೆ.",
        "GATE ಪರೀಕ್ಷೆಯ ಮೂಲಕ PSU ಗಳಲ್ಲಿ ನೇಮಕಾತಿ ಹೊಂದುವುದು ಕೋರ್ ವಲಯದ ಉತ್ತಮ ಮಾರ್ಗವಾಗಿದೆ.",
        "ನಿಮ್ಮ ನಿರ್ದಿಷ್ಟ ಕ್ಷೇತ್ರದಲ್ಲಿ ಉತ್ತಮ ಲ್ಯಾಬ್‌ಗಳು ಮತ್ತು ಉದ್ಯಮ ಸಂಪರ್ಕ ಇರುವ ಕಾಲೇಜುಗಳನ್ನು ಹುಡುಕಿ.",
      ],
      undecided: [
        "ಹೆಚ್ಚಿನ IITs ಗಳಲ್ಲಿ ಮೊದಲ ವರ್ಷದ ನಂತರ ನಿಮ್ಮ ಅಂಕಗಳ ಆಧಾರದ ಮೇಲೆ ಬ್ರಾಂಚ್ ಬದಲಾಯಿಸಲು ಅವಕಾಶವಿರುತ್ತದೆ.",
        "ವಿಸ್ತೃತ ವ್ಯಾಪ್ತಿಯ ಬ್ರಾಂಚ್‌ಗಳು (EE, ಮೆಕ್ಯಾನಿಕಲ್, ಇಂಜಿನಿಯರಿಂಗ್ ಫಿಸಿಕ್ಸ್) ಭವಿಷ್ಯಕ್ಕಾಗಿ ಹೆಚ್ಚು ದಾರಿಗಳನ್ನು ಮುಕ್ತವಾಗಿಡುತ್ತವೆ.",
        "ನಿಮ್ಮ ಆದ್ಯತೆಗಳನ್ನು ಅಂತಿಮಗೊಳಿಸುವ ಮೊದಲು ಸೀನಿಯರ್ ವಿದ್ಯಾರ್ಥಿಗಳೊಂದಿಗೆ ಮಾತನಾಡಿ.",
      ],
    },
    quota: {
      AI: "ಆಲ್ ಇಂಡಿಯಾ ಸೀಟ್", HS: "ತವರು ರಾಜ್ಯ ಕೋಟಾ", OS: "ಇತರ ರಾಜ್ಯ ಕೋಟಾ",
      GO: "ಗೋವಾ ಕೋಟಾ", JK: "ಜೆ & ಕೆ ಕೋಟಾ", LA: "ಲಡಾಖ್ ಕೋಟಾ",
    },
    loading: [
      "ಕಡೆ ವರ್ಷದ ಕಟ್‌ಆಫ್ ಓದಲಾಗುತ್ತಿದೆ…",
      "ನಿಮ್ಮ ಪ್ರೊಫೈಲ್‌ಗೆ ಹೊಂದಾಣಿಕೆಯಾಗುವ ಕಾಲೇಜುಗಳನ್ನು ಹುಡುಕಲಾಗುತ್ತಿದೆ…",
      "Safe, Target ಮತ್ತು Reach ವರ್ಗೀಕರಿಸಲಾಗುತ್ತಿದೆ…",
    ],
    error: {
      title: "ಪ್ರಕ್ರಿಯೆ ಪೂರ್ಣಗೊಳ್ಳಲಿಲ್ಲ",
      generic: "ಏನೋ ತೊಂದರೆಯಾಗಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
      retry: "ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ",
      edit: "ನನ್ನ ವಿವರಗಳನ್ನು ಬದಲಾಯಿಸಿ",
    },
    review: {
      mains: "JEE Main ರ‍್ಯಾಂಕ್", adv: "JEE Advanced ರ‍್ಯಾಂಕ್", gender: "ಲಿಂಗ",
      category: "ವರ್ಗ", state: "ತವರು ರಾಜ್ಯ", income: "ಕುಟುಂಬದ ಆದಾಯ", goal: "ಗುರಿ", branch: "ಬ್ರಾಂಚ್",
      anyBranch: "ಯಾವುದಾದರೂ ಬ್ರಾಂಚ್", notGiven: "ನೀಡಿಲ್ಲ", dash: "—",
    },
    income: {
      below_3l: "₹3 ಲಕ್ಷಕ್ಕಿಂತ ಕಡಿಮೆ",
      "3l_5l": "₹3 ಲಕ್ಷ - ₹5 ಲಕ್ಷ",
      above_5l: "₹5 ಲಕ್ಷಕ್ಕಿಂತ ಹೆಚ್ಚು",
      below3l: "₹3 ಲಕ್ಷ/ವರ್ಷಕ್ಕಿಂತ ಕಡಿಮೆ",
      below3lSub: "100% IIT/NIT ಬೋಧನಾ ಶುಲ್ಕ ವಿನಾಯಿತಿಗೆ ಅರ್ಹರು",
      "3l5l": "₹3 ಲಕ್ಷ ಮತ್ತು ₹5 ಲಕ್ಷ/ವರ್ಷದ ನಡುವೆ",
      "3l5lSub": "IITs ಮತ್ತು NITs ಗಳಲ್ಲಿ 2/3 ಬೋಧನಾ ಶುಲ್ಕ ವಿನಾಯಿತಿಗೆ ಅರ್ಹರು",
      above5l: "₹5 ಲಕ್ಷ/ವರ್ಷಕ್ಕಿಂತ ಹೆಚ್ಚು",
      above5lSub: "ಸಾಮಾನ್ಯ ಶುಲ್ಕ ಅನ್ವಯಿಸುತ್ತದೆ",
    },
    region: {
      all: "ಆಲ್ ಇಂಡಿಯಾ",
      metro: "ಮೆಟ್ರೋ ನಗರಗಳು ಮಾತ್ರ",
      north: "ಉತ್ತರ ಭಾರತ",
      south: "ದಕ್ಷಿಣ ಭಾರತ",
      east: "ಪೂರ್ವ ಭಾರತ",
      west: "ಪಶ್ಚಿಮ ಭಾರತ",
      northeast: "ಈಶಾನ್ಯ / ಗುಡ್ಡಗಾಡು ಪ್ರಾಂತ್ಯ",
    },
    panel: {
      toggle: "ಫಿಲ್ಟರ್ / ಬದಲಾಯಿಸಿ",
      title: "ನಿಮ್ಮ ವಿವರಗಳು",
      subtitle: "ಯಾವುದನ್ನಾದರೂ ಬದಲಾಯಿಸಿ — ಫಲಿತಾಂಶಗಳು ತಕ್ಷಣ ಅಪ್ಡೇಟ್ ಆಗುತ್ತವೆ.",
      mainsLabel: "JEE Main ರ‍್ಯಾಂಕ್",
      mainsPlaceholder: "ಉದಾ: 12,500",
      incomeLabel: "ಕುಟುಂಬದ ಆದಾಯ",
      ratioLabel: "ಕಾಲೇಜು ವರ್ಸಸ್ ಬ್ರಾಂಚ್ ಆದ್ಯತೆ",
      ratioBranch: "ಬ್ರಾಂಚ್ ಗೆ ಆದ್ಯತೆ",
      ratioBrand: "ಕಾಲೇಜು ಬ್ರಾಂಡ್ ಗೆ ಆದ್ಯತೆ",
      regionLabel: "ಭೌಗೋಳಿಕ ಪ್ರದೇಶ",
      advLabel: "JEE Advanced ರ‍್ಯಾಂಕ್",
      advPlaceholder: "ಐಚ್ಛಿಕ",
      genderLabel: "ಲಿಂಗ",
      categoryLabel: "ವರ್ಗ",
      stateLabel: "ತವರು ರಾಜ್ಯ",
      goalLabel: "ವೃತ್ತಿ ಗುರಿ",
      branchLabel: "ಬ್ರಾಂಚ್ ಆದ್ಯತೆ",
      updating: "ಅಪ್ಡೇಟ್ ಆಗುತ್ತಿದೆ…",
      done: "ಮುಗಿಯಿತು",
    },
    results: {
      standingTitle: "ನಿಮ್ಮ ಸ್ಥಾನಮಾನ",
      byBranch: "ಬ್ರಾಂಚ್ ಪ್ರಕಾರ",
      byCollege: "ಕಾಲೇಜು ಪ್ರಕಾರ",
      edit: "ಬದಲಾಯಿಸಿ",
      share: "ಹಂಚಿಕೊಳ್ಳಿ",
      copyLink: "ಲಿಂಕ್ ಕಾಪಿ ಮಾಡಿ",
      copied: "ಕಾಪಿ ಮಾಡಲಾಗಿದೆ!",
      print: "ಪ್ರಿಂಟ್ / PDF ಉಳಿಸಿ",
      noteEyebrow: "ನಿಮಗಾಗಿ ಒಂದು ಟಿಪ್ಪಣಿ",
      noteHeadlineDefault: "ನಿಮ್ಮ ನಿರೀಕ್ಷಿತ ಸ್ಥಾನ ಇಲ್ಲಿದೆ.",
      searchPlaceholder: "ಕಾಲೇಜು ಅಥವಾ ಬ್ರಾಂಚ್ ಹುಡುಕಿ…",
      searchAria: "ಫಲಿತಾಂಶಗಳನ್ನು ಹುಡುಕಿ",
      typeAll: "ಎಲ್ಲವೂ",
      emptyFilteredTitle: "ಯಾವುದೇ ಹೊಂದಾಣಿಕೆಗಳು ಕಂಡುಬಂದಿಲ್ಲ.",
      emptyFilteredBody: "ಹುಡುಕಾಟದ ಪದಗಳನ್ನು ಬದಲಾಯಿಸಿ ಅಥವಾ ಎಲ್ಲಾ ಕಾಲೇಜುಗಳನ್ನು ತೋರಿಸಿ.",
      clearFilters: "Filter ಗಳನ್ನು ತೆರವುಗೊಳಿಸಿ",
      emptyResultsTitle: "ನಿಖರವಾದ ಹೊಂದಾಣಿಕೆಗಳು ಸಿಗಲಿಲ್ಲ.",
      emptyResultsBody: "ಆಯ್ದ ಫಿಲ್ಟರ್‌ಗಳಿಗೆ ಈ ಡೇಟಾಬೇಸ್‌ನಲ್ಲಿ ನಿಮ್ಮ ರ‍್ಯಾಂಕ್ ಹೊಂದಿಕೆಯಾಗುತ್ತಿಲ್ಲ. ನಿಮ್ಮ ಇನ್ನೊಂದು ರ‍್ಯಾಂಕ್ ಸೇರಿಸಿ ಅಥವಾ ತವರು ರಾಜ್ಯವನ್ನು ಪರಿಶೀಲಿಸಿ.",
      emptyEdit: "ನನ್ನ ವಿವರಗಳನ್ನು ಬದಲಾಯಿಸಿ",
      profileMain: "Main",
      profileAdvanced: "Advanced",
      disclaimerHtml:
        "OPEN (CRL) ಸೀಟುಗಳಿಗಾಗಿ JoSAA 2025 ರೌಂಡ್-6 ಕಟ್‌ಆಫ್ ಆಧಾರಿತ. ಕಟ್‌ಆಫ್ ಪ್ರತಿ ವರ್ಷ ಬದಲಾಗುತ್ತದೆ — " +
        "ಇದನ್ನು ಮಾರ್ಗದರ್ಶಿ ಎಂದು ತಿಳಿಯಿರಿ, ಅಂತಿಮ ಒಪ್ಪಂದವಲ್ಲ. ಸೀಟು ಲಾಕ್ ಮಾಡುವ ಮುನ್ನ <strong>josaa.nic.in</strong> ನಲ್ಲಿ ಪರಿಶೀಲಿಸಿ. " +
        "ಟಿಪ್ಪಣಿ: ಅಧಿಕೃತ JEE ಕಟ್‌ಆಫ್ ಡೇಟಾದ ಆಧಾರದ ಮೇಲೆ ನಿಖರವಾದ ಪ್ರವೇಶ ವಿವರ ನೀಡುವುದು ನಮ್ಮ ಉದ್ದೇಶವಾಗಿದೆ, ಆದ್ದರಿಂದ ಇಲ್ಲಿ ಶುಲ್ಕದ ವಿವರ ಇರುವುದಿಲ್ಲ. ಶುಲ್ಕದ ವಿವರಗಳಿಗಾಗಿ ಆಯಾ ಕಾಲೇಜಿನ ಅಧಿಕೃತ ವೆಬ್‌ಸೈಟ್ ನೋಡಿ.",
    },
    headlines: {
      adjust: "ವಿವರಗಳನ್ನು ಸ್ವಲ್ಪ ಸರಿಪಡಿಸೋಣ.",
      good: "ನೀವು ಉತ್ತಮ ಸ್ಥಾನದಲ್ಲಿದ್ದೀರಿ.",
      options: "ನಿಮ್ಮ ಮುಂದೆ ಉತ್ತಮ ಆಯ್ಕೆಗಳಿವೆ.",
      solid: "ನಿಮ್ಮ ಭವಿಷ್ಯ ನಿರ್ಮಿಸಲು ಉತ್ತಮ ಅಡಿಪಾಯವಿದೆ.",
      stretch: "ಸ್ವಲ್ಪ ಕಷ್ಟ — ಆದರೆ ಅಸಾಧ್ಯವಲ್ಲ.",
    },
    zones: {
      safeName: "Safe", safeSub: "ಬಲವಾದ ಬ್ಯಾಕಪ್",
      targetName: "Target", targetSub: "ನಿಮ್ಮ ಉತ್ತಮ ಹೊಂದಾಣಿಕೆ ವಲಯ",
      reachName: "Reach", reachSub: "ಪ್ರಯತ್ನಿಸಬಹುದಾದ",
    },
    ruler: {
      introEyebrow: "ಸಂಪೂರ್ಣ ಚಿತ್ರಣ",
      lede: "ಒಂದೇ ಸ್ಕೇಲ್‌ನಲ್ಲಿ ಎಲ್ಲಾ ಫಲಿತಾಂಶಗಳು — ಕಡು ಬಣ್ಣದ ಗೆರೆ ನಿಮ್ಮದು. ಸ್ಕೇಲ್ logarithmic ಆಗಿದೆ, ಇದರಿಂದಾಗಿ ಗೀಚು ರ‍್ಯಾಂಕ್‌ಗಳೂ ಓದಲು ಸುಲಭವಾಗಿವೆ.",
      iitTitle: "IITs", iitVia: "JEE Advanced ಮೂಲಕ",
      nitTitle: "NITs · IIITs · GFTIs", nitVia: "JEE Main ಮೂಲಕ",
      options: "ಆಯ್ಕೆಗಳು",
      you: "ನೀವು",
      yourRank: "ನಿಮ್ಮ ರ‍್ಯಾಂಕ್: {rank}",
      closes: "ಮುಚ್ಚುತ್ತದೆ",
    },
    section: {
      Target: "Target", Reach: "Reach", Safe: "Safe",
    },
    rankbar: {
      opens: "ತೆರೆಯುತ್ತದೆ", closes: "ಮುಚ್ಚುತ್ತದೆ",
      safe: "ನೀವು: {rank} — ಕಳೆದ ವರ್ಷದ ಓಪನಿಂಗ್ ರ‍್ಯಾಂಕ್‌ಗಿಂತ ಮುಂದೆ.",
      targetComfort: "ನೀವು: {rank} — ಕಳೆದ ವರ್ಷದ ರೇಂಜ್ ನಡುವೆ.",
      targetEdge: "ನೀವು: {rank} — ರೇಂಜ್ ಒಳಗಡೆ, ಆದರೆ ಕೊನೆಗೆ ಹತ್ತಿರ.",
      reach: "ನೀವು: {rank} — ಕಳೆದ ವರ್ಷದ ಕ್ಲೋಸಿಂಗ್ ರ‍್ಯಾಂಕ್‌ಗಿಂತ ಸುಮಾರು {past}% ಮುಂದೆ. ಕಟ್‌ಆಫ್ ಬದಲಾಗುತ್ತದೆ.",
    },
    confidence: {
      highLabel: "ಸ್ಥಿರ ಕಟ್‌ಆಫ್", highHint: "ಕಳೆದ ವರ್ಷದ ವಿಸ್ತಾರವಾದ ಶ್ರೇಣಿ — ಬದಲಾಗುವ ಸಾಧ್ಯತೆ ಕಡಿಮೆ.",
      mediumLabel: "ಸಾಧಾರಣ ಸ್ಥಿರ", mediumHint: "ಕಳೆದ ವರ್ಷದ ಶ್ರೇಣಿ ಸಾಧಾರಣವಾಗಿದೆ — ಆವರೇಜ್ ರಿಸ್ಕ್.",
      fragileLabel: "ಅಸ್ಥಿರ ಕಟ್‌ಆಫ್", fragileHint: "ಕಳೆದ ವರ್ಷದ ಕಿರಿದಾದ ಶ್ರೇಣಿ — ಕಟ್‌ಆಫ್ ಬೇಗ ಬದಲಾಗಬಹುದು.",
    },
    card: {
      fitsGoal: "ನಿಮ್ಮ ಗುರಿಗೆ ಹೊಂದುತ್ತದೆ",
      fitsGoalTitle: "ನಿಮ್ಮ ಆಸಕ್ತಿಯ ವಲಯಕ್ಕೆ ಸೂಕ್ತ ಹೊಂದಾಣಿಕೆ",
      dualDegree: "ಡ್ಯುಯಲ್ ಡಿಗ್ರಿ (5 ವರ್ಷ)",
      femaleSeat: "ಮಹಿಳೆಯರಿಗೆ ಮಾತ್ರ ಇರುವ ಸೀಟು",
      viaAdvanced: "JEE Advanced ಮೂಲಕ",
      viaMains: "JEE Main ಮೂಲಕ",
      homeBadge: "ತವರು ರಾಜ್ಯ: ~{n} ರ‍್ಯಾಂಕ್ ಗಳ ಉಳಿತಾಯ",
      homeBadgeTitle: "ತವರು ರಾಜ್ಯ ಕೋಟಾ ಇತರ ಸೀಟುಗಳಿಗಿಂತ ಇಷ್ಟು ರ‍್ಯಾಂಕ್ ತಡವಾಗಿ ಮುಚ್ಚುತ್ತದೆ.",
      femaleBadge: "ಮಹಿಳಾ ಸೀಟು: ~{n} ರ‍್ಯಾಂಕ್ ಗಳ ನಂತರ",
      femaleBadgeTitle: "ಮಹಿಳಾ ಮೀಸಲು ಸೀಟು ಜನರಲ್ ಸೀಟುಗಳಿಗಿಂತ ಇಷ್ಟು ರ‍್ಯಾಂಕ್ ತಡವಾಗಿ ಮುಚ್ಚುತ್ತದೆ.",
      chance: "ಸಾಧ್ಯತೆ",
      probTitle: "ನಿರೀಕ್ಷಿತ ಪ್ರವೇಶ ಸಾಧ್ಯತೆ: {prob}%",
      historyBtn: "ಕಟ್‌ಆಫ್ ಇತಿಹಾಸ ನೋಡಿ",
      historyBtnClose: "ಕಟ್‌ಆಫ್ ಇತಿಹಾಸ ಮರೆಮಾಡಿ",
    },
    footer: {
      aboutHtml: "Disha — <a href=\"https://www.utmt.org\" target=\"_blank\" rel=\"noopener\">UTMT</a> ನ ಉಪಕ್ರಮ, JEE ಅಭ್ಯರ್ಥಿಗಳಿಗೆ ಕಾಳಜಿಯಿಂದ ರೂಪಿಸಲಾಗಿದೆ",
      openSource: "ಮುಕ್ತ ಆಕರ · ಉಚಿತ · ಲಾಗಿನ್ ಇಲ್ಲ",
      dataHtml: "ಕಟ್‌ಆಫ್ ಡೇಟಾ: <a href=\"https://github.com/atmabodha/OpenNLP\" target=\"_blank\" rel=\"noopener\">OpenNLP (JoSAA 2025)</a>",
    },
    share: {
      title: "Disha — ನನ್ನ JEE ಕಾಲೇಜು ಪಂದ್ಯಗಳು",
      targetLine: "Target ({count}): {picks}",
      countsLine: "Safe {safe} · Reach {reach}",
      noTarget: "ಉನ್ನತ ಕಾಲೇಜುಗಳು: {picks}",
      open: "Disha ತೆರೆಯಿರಿ:",
      copyFail: "ಕಾಪಿ ಮಾಡಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ಲಿಂಕ್ ಕಾಪಿ ಮಾಡಲು ಅಡ್ರೆಸ್ ಬಾರ್ ಪ್ರೆಸ್ ಮಾಡಿ ಹಿಡಿಯಿರಿ.",
    },
    errors: {
      unreachable: "ಸಂಪರ್ಕ ಸೇವೆಯನ್ನು ಪಡೆಯಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ನೀವು ಆಫ್‌ಲೈನ್ ಇರಬಹುದು — ಕನೆಕ್ಷನ್ ಪರಿಶೀಲಿಸಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
      requestFailed: "status {status} ನೊಂದಿಗೆ ವಿನಂತಿ ವಿಫಲವಾಗಿದೆ.",
    },
  },
};

// ── Language state ──────────────────────────────────────────────────────

function getLang() {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    if (saved && SUPPORTED_LANGS.includes(saved)) return saved;
  } catch (_) { /* localStorage unavailable */ }
  return "en";
}

function setLang(lang) {
  if (!SUPPORTED_LANGS.includes(lang)) lang = "en";
  try { localStorage.setItem(LANG_KEY, lang); } catch (_) { /* ignore */ }
  document.documentElement.lang = lang;
}

// ── Lookup ──────────────────────────────────────────────────────────────

function resolvePath(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

// t("flow.s1Title") or t("card.homeBadge", { n: "1,200" })
function t(path, vars) {
  const lang = getLang();
  let val = resolvePath(I18N[lang], path);
  if (val === undefined) val = resolvePath(I18N.en, path);
  if (val === undefined) return path;
  if (typeof val === "string" && vars) {
    val = val.replace(/\{(\w+)\}/g, (m, k) => (vars[k] != null ? vars[k] : m));
  }
  return val;
}

// ── Static DOM application ────────────────────────────────────────────────
// Elements opt in with:
//   data-i18n="key"        → textContent
//   data-i18n-html="key"   → innerHTML (for strings with markup)
//   data-i18n-ph="key"     → placeholder attribute
//   data-i18n-aria="key"   → aria-label attribute
//   data-i18n-title="key"  → title attribute

function applyStaticI18n(root) {
  const scope = root || document;
  scope.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  scope.querySelectorAll("[data-i18n-html]").forEach((el) => {
    el.innerHTML = t(el.getAttribute("data-i18n-html"));
  });
  scope.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    el.setAttribute("placeholder", t(el.getAttribute("data-i18n-ph")));
  });
  scope.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
  });
  scope.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.setAttribute("title", t(el.getAttribute("data-i18n-title")));
  });
}
