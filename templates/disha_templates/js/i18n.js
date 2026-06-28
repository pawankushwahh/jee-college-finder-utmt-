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
const SUPPORTED_LANGS = ["en", "hi"];

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
