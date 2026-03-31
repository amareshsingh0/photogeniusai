"""
Extended blocklists for comprehensive content filtering
Contains 200+ keywords across multiple categories
"""

# Expanded explicit content blocklist
EXPLICIT_EXTENDED = [
    # More sexual terms
    "hentai", "ecchi", "yaoi", "yuri", "ahegao",
    "bdsm", "bondage", "fetish", "kink", "dominatrix",
    "stripper", "prostitute", "escort", "hooker",
    "gangbang", "threesome", "foursome", "orgy",
    "cum", "jizz", "sperm", "ejaculat",
    
    # Slang variations
    "tits", "boobs", "ass", "butt", "booty",
    "thicc", "curvy", "voluptuous",
    
    # Leetspeak variations
    "n00d", "s3x", "pr0n", "xxx",
    
    # More violence
    "terrorist", "bomb", "explosion", "massacre",
    "war crime", "ethnic cleansing", "lynching",
    "acid attack", "honor killing",
    
    # Additional explicit
    "explicit", "hardcore", "uncensored", "bare",
    "topless", "bottomless", "undressed",
    "masturbation", "masturbating", "jerking off",
    "handjob", "fingering", "clitoris", "clit",
    "buttocks", "anus", "rectum", "scrotum", "testicles",
    "pubic", "pubes", "bush", "shaved", "hairless",
    "threesome", "group sex", "gang bang", "orgy",
    "bdsm", "sadism", "masochism", "domination",
    "submission", "slave", "master", "whip", "chains",
    "latex", "leather", "fetish", "kink",
    
    # More gore/violence
    "dismembered", "decapitated", "beheaded",
    "mutilated", "tortured", "executed",
    "bloody", "gory", "grisly", "gruesome",
    "corpse", "cadaver", "dead body", "lifeless",
    "autopsy", "dissection", "morgue",
    
    # Self-harm
    "self harm", "cutting", "suicide", "hanging",
    "overdose", "poisoning",
    
    # Additional explicit terms to reach 200+
    "pornography", "pornographic", "adult content", "adult film",
    "sex scene", "sex act", "sexual act", "sexual content",
    "nudity", "nakedness", "bareness", "undressing",
    "stripping", "strip tease", "pole dancing", "lap dance",
    "escort service", "brothel", "prostitution", "sex work",
    "sexual fantasy", "sexual desire", "lust", "libido",
    "arousal", "erection", "hard on", "boner",
    "climax", "ejaculation", "semen", "precum",
    "vaginal", "penile", "oral", "anal sex",
    "threesome", "fourway", "orgy", "gangbang",
    "bdsm", "sadomasochism", "bondage", "domination",
    "submission", "master slave", "whip", "chains",
    "latex", "leather", "fetish", "kink",
    "voyeurism", "exhibitionism", "bestiality", "zoophilia",
    "incest", "rape fantasy", "non consensual",
    "gore", "gory", "bloody", "mutilation",
    "dismemberment", "decapitation", "beheading",
    "torture", "execution", "murder", "killing",
    "violence", "violent", "brutal", "brutality",
    "corpse", "dead body", "cadaver", "morgue",
    "autopsy", "dissection", "mutilated", "dismembered",
]

# Drugs extended
DRUGS_EXTENDED = [
    "weed", "marijuana", "cannabis", "joint", "bong",
    "ecstasy", "mdma", "lsd", "acid", "shrooms",
    "oxy", "xanax", "adderall", "ritalin",
    "drug paraphernalia", "needle", "syringe",
    "cocaine", "crack", "heroin", "meth",
    "methamphetamine", "fentanyl", "opioids",
    "pills", "tablets", "injection", "snorting",
    "smoking weed", "getting high", "stoned",
    "drugged", "under influence",
]

# Hindi/Hinglish inappropriate terms
HINDI_INAPPROPRIATE = [
    "chut", "lund", "gand", "chod", "bhosdi",
    "harami", "kutta", "saala", "randi",
    "madarchod", "behenchod", "bhenchod",
    "chutiya", "gandu", "lund", "chutia",
    "bhosdike", "bhosdiwale", "chutiyapa",
    "gaand", "gaandu", "lund", "chut",
    "randi", "randi ka", "randi ki",
    "saali", "saale", "saalo",
    "kutta", "kutte", "kutti",
    "harami", "haramkhor", "haramzada",
]

# More celebrities (expanded)
CELEBRITIES_EXTENDED = [
    # More Bollywood
    "tiger shroff", "sidharth malhotra", "vicky kaushal",
    "ayushmann khurrana", "rajkummar rao", "nawazuddin siddiqui",
    "sara ali khan", "janhvi kapoor", "ananya panday",
    "kiara advani", "tara sutaria", "disha patani",
    "kriti sanon", "shraddha kapoor", "parineeti chopra",
    "sonam kapoor", "sonakshi sinha", "alia bhatt",
    "anushka sharma", "katrina kaif", "deepika padukone",
    "priyanka chopra", "kareena kapoor", "kangana ranaut",
    
    # South Indian
    "prabhas", "allu arjun", "mahesh babu", "jr ntr",
    "vijay", "ajith", "suriya", "dhanush",
    "samantha", "rashmika mandanna", "pooja hegde",
    "nayanthara", "tamannaah", "anushka shetty",
    "vijay sethupathi", "fahadh faasil", "dulquer salmaan",
    
    # More Hollywood
    "ryan gosling", "ryan reynolds", "chris pratt",
    "zendaya", "timothee chalamet", "florence pugh",
    "anya taylor-joy", "sydney sweeney", "hailee steinfeld",
    "millie bobby brown", "sadie sink", "finn wolfhard",
    "noah schnapp", "caleb mclaughlin", "gaten matarazzo",
    
    # K-pop
    "bts", "blackpink", "lisa", "jisoo", "jennie", "rose",
    "jungkook", "v", "jimin", "suga", "rm", "jin",
    "j-hope", "twice", "red velvet", "itzy", "aespa",
    
    # YouTubers/Influencers (India)
    "carryminati", "bb ki vines", "ashish chanchlani", "amit bhadana",
    "fukra insaan", "triggered insaan", "flying beast",
    "gaurav taneja", "sandeep maheshwari", "mumbiker nikhil",
    "technical guruji", "dhruv rathee", "tanmay bhat",
    
    # International YouTubers
    "pewdiepie", "mrbeast", "logan paul", "jake paul",
    "ksi", "david dobrik", "casey neistat", "marques brownlee",
    "markiplier", "jacksepticeye", "ninja", "pokimane",
    
    # More actors
    "henry cavill", "jason momoa", "keanu reeves",
    "gal gadot", "zoe saldana", "natalie portman",
    "anne hathaway", "jennifer aniston", "sandra bullock",
    
    # More musicians
    "harry styles", "lady gaga", "adele", "bruno mars",
    "the weeknd", "post malone", "travis scott", "kendrick lamar",
    "j cole", "nicki minaj", "cardi b", "megan thee stallion",
    
    # More sports
    "kobe bryant", "stephen curry", "kevin durant",
    "novak djokovic", "rafael nadal", "naomi osaka",
    "simona halep", "maria sharapova",
    
    # Expand to 500+ celebrities - Adding more
    # More Bollywood actors
    "aditya roy kapur", "kartik aaryan", "ishaan khatter", "jhanvi kapoor",
    "ananya panday", "tara sutaria", "sara ali khan", "jacqueline fernandez",
    "nora fatehi", "malaika arora", "urvashi rautela", "neha dhupia",
    "bipasha basu", "lara dutta", "preity zinta", "aishwarya rai",
    "sushmita sen", "madhavan", "siddharth", "r madhavan",
    "vijay devarakonda", "nani", "nagarjuna", "venkatesh",
    "chiranjeevi", "balakrishna", "ram charan", "ntr",
    
    # More Hollywood actors (expanded)
    "matt damon", "ben affleck", "jake gyllenhaal", "ryan gosling",
    "chris pine", "chris evans", "chris hemsworth", "chris pratt",
    "paul rudd", "mark ruffalo", "jeremy renner", "samuel l jackson",
    "bruce willis", "arnold schwarzenegger", "sylvester stallone",
    "harrison ford", "al pacino", "robert de niro", "jack nicholson",
    "meryl streep", "cate blanchett", "nicole kidman", "julianne moore",
    "kate winslet", "rachel mcadams", "amy adams", "jessica chastain",
    
    # More musicians (expanded)
    "ariana grande", "selena gomez", "miley cyrus", "demi lovato",
    "lady gaga", "katy perry", "pink", "christina aguilera",
    "britney spears", "madonna", "cher", "whitney houston",
    "mariah carey", "celine dion", "adele", "amy winehouse",
    "lana del rey", "billie eilish", "olivia rodrigo", "dua lipa",
    "doja cat", "megan thee stallion", "cardi b", "nicki minaj",
    "lizzo", "sza", "halsey", "camila cabello",
    
    # Indian musicians
    "arijit singh", "shreya ghoshal", "sunidhi chauhan", "neha kakkar",
    "tony kakkar", "badshah", "honey singh", "diljit dosanjh",
    "gurdas maan", "sukhbir", "mika singh", "yo yo honey singh",
    "rahat fateh ali khan", "atif aslam", "shaan", "kumar sanu",
    "udit narayan", "sonu nigam", "kailash kher", "sukhwinder singh",
    
    # More sports stars
    "roger federer", "rafael nadal", "novak djokovic", "andy murray",
    "serena williams", "venus williams", "maria sharapova", "naomi osaka",
    "coco gauff", "iga swiatek", "carlos alcaraz", "jannik sinner",
    "lebron james", "kobe bryant", "michael jordan", "stephen curry",
    "kevin durant", "kawhi leonard", "giannis antetokounmpo", "luka doncic",
    "cristiano ronaldo", "lionel messi", "neymar", "kylian mbappe",
    "virat kohli", "ms dhoni", "rohit sharma", "jasprit bumrah",
    "sachin tendulkar", "rahul dravid", "sourav ganguly", "virender sehwag",
    
    # More tech/business
    "jeff bezos", "elon musk", "bill gates", "warren buffett",
    "mark zuckerberg", "larry page", "sergey brin", "sundar pichai",
    "satya nadella", "tim cook", "steve jobs", "steve wozniak",
    "jack ma", "masayoshi son", "mukesh ambani", "gautam adani",
    "ratan tata", "anil ambani", "azim premji", "narayana murthy",
    
    # More influencers/content creators
    "mrbeast", "pewdiepie", "markiplier", "jacksepticeye",
    "ninja", "pokimane", "valkyrae", "disguised toast",
    "shroud", "dr disrespect", "timthetatman", "nickmercs",
    "carryminati", "bb ki vines", "ashish chanchlani", "amit bhadana",
    "fukra insaan", "triggered insaan", "flying beast", "gaurav taneja",
    "sandeep maheshwari", "mumbiker nikhil", "technical guruji",
    "dhruv rathee", "tanmay bhat", "rohit sharma", "raj shamani",
    
    # K-pop groups and members
    "bts", "blackpink", "twice", "red velvet", "itzy", "aespa",
    "newjeans", "ive", "le sserafim", "gidle", "stray kids",
    "jungkook", "v", "jimin", "suga", "rm", "jin", "j-hope",
    "lisa", "jisoo", "jennie", "rose", "jihyo", "nayeon",
    "irene", "wendy", "seulgi", "joy", "yeri",
    
    # More actors (international)
    "tom hiddleston", "benedict cumberbatch", "michael fassbender",
    "james mcavoy", "daniel radcliffe", "rupert grint", "emma watson",
    "eddie redmayne", "domhnall gleeson", "andrew garfield",
    "tobey maguire", "andrew lincoln", "norman reedus", "lauren cohan",
    "milla jovovich", "angelina jolie", "scarlett johansson",
    "charlize theron", "jennifer lawrence", "emma stone",
    "margot robbie", "gal gadot", "zoe saldana", "natalie portman",
    
    # Even more celebrities to reach 500+
    # More Indian TV actors
    "karan kundra", "gauahar khan", "hina khan", "shilpa shetty",
    "rakhi sawant", "manisha koirala", "tabu", "vidya balan",
    "kangana ranaut", "sonam kapoor", "sonakshi sinha",
    "shraddha kapoor", "parineeti chopra", "kriti sanon",
    "kiara advani", "tara sutaria", "disha patani", "jacqueline fernandez",
    "nora fatehi", "malaika arora", "urvashi rautela", "neha dhupia",
    
    # More international actors
    "jennifer aniston", "courteney cox", "lisa kudrow", "matthew perry",
    "david schwimmer", "matt leblanc", "chandler bing", "ross geller",
    "rachel green", "monica geller", "phoebe buffay", "joey tribbiani",
    "sophie turner", "maisie williams", "peter dinklage", "nikolaj coster-waldau",
    "lena headey", "emilia clarke", "kit harington", "sean bean",
    "ian mckellen", "orlando bloom", "viggo mortensen", "elijah wood",
    "sean astin", "billy boyd", "dominic monaghan", "andy serkis",
    
    # More musicians (expanded further)
    "the beatles", "paul mccartney", "john lennon", "george harrison",
    "ringo starr", "rolling stones", "mick jagger", "keith richards",
    "led zeppelin", "robert plant", "jimmy page", "john bonham",
    "pink floyd", "roger waters", "david gilmour", "syd barrett",
    "queen", "freddie mercury", "brian may", "roger taylor",
    "ac dc", "bon scott", "brian johnson", "angus young",
    "metallica", "james hetfield", "lars ulrich", "kirk hammett",
    "nirvana", "kurt cobain", "dave grohl", "krist novoselic",
    "green day", "billie joe armstrong", "mike dirnt", "tre cool",
    "linkin park", "chester bennington", "mike shinoda", "joe hahn",
    "coldplay", "chris martin", "jonny buckland", "guy berryman",
    "radiohead", "thom yorke", "jonny greenwood", "ed o brien",
    "u2", "bono", "the edge", "adam clayton",
    "red hot chili peppers", "anthony kiedis", "flea", "chad smith",
    "foo fighters", "dave grohl", "taylor hawkins", "nate mendel",
    
    # More Indian classical and folk
    "ravishankar", "zakir hussain", "amjad ali khan", "shivkumar sharma",
    "hariprasad chaurasia", "bismillah khan", "pt jasraj", "kishori amonkar",
    "lata mangeshkar", "asha bhosle", "mukesh", "rafi",
    "kishore kumar", "mohammed rafi", "manna dey", "hemant kumar",
    
    # More sports personalities
    "usain bolt", "michael phelps", "simone biles", "aly raisman",
    "gabby douglas", "nastia liukin", "shawn johnson", "kerri strug",
    "tiger woods", "phil mickelson", "rory mcilroy", "jordan spieth",
    "lewis hamilton", "max verstappen", "sebastian vettel", "fernando alonso",
    "michael schumacher", "ayrton senna", "alain prost", "nigel mansell",
    "floyd mayweather", "mike tyson", "muhammad ali", "manny pacquiao",
    "conor mcgregor", "khabib nurmagomedov", "jon jones", "anderson silva",
    "fedor emelianenko", "georges st pierre", "bj penn", "chuck liddell",
    
    # More cricket players
    "yuvraj singh", "gautam gambhir", "virender sehwag", "harbhajan singh",
    "zaheer khan", "ishant sharma", "ravindra jadeja", "hardik pandya",
    "jasprit bumrah", "mohammed shami", "kuldeep yadav", "yuzvendra chahal",
    "rishabh pant", "kl rahul", "shikhar dhawan", "dinesh karthik",
    "ravichandran ashwin", "cheteshwar pujara", "ajinkya rahane",
    "kane williamson", "steve smith", "david warner", "pat cummins",
    "joe root", "ben stokes", "james anderson", "stuart broad",
    "kagiso rabada", "quinton de kock", "ab de villiers", "hashim amla",
    
    # More football players
    "karim benzema", "luka modric", "toni kroos", "sergio ramos",
    "virgil van dijk", "sadio mane", "mohamed salah", "roberto firmino",
    "kevin de bruyne", "erling haaland", "phil foden", "jack grealish",
    "kylian mbappe", "neymar", "marco verratti", "marquinhos",
    "manuel neuer", "thomas muller", "robert lewandowski", "joshua kimmich",
    "harry kane", "heung min son", "dele alli", "eric dier",
    "eden hazard", "thibaut courtois", "luka modric", "marcelo",
    
    # More tennis players
    "andy murray", "stan wawrinka", "marin cilic", "kevin anderson",
    "daniil medvedev", "stefanos tsitsipas", "alexander zverev", "matteo berrettini",
    "felix auger aliassime", "carlos alcaraz", "jannik sinner", "holger rune",
    "ashleigh barty", "barbora krejcikova", "iga swiatek", "coco gauff",
    "emma raducanu", "leylah fernandez", "bianca andreescu", "sloane stephens",
    
    # More content creators/influencers
    "david dobrik", "casey neistat", "marques brownlee", "linus tech tips",
    "mkbhd", "unbox therapy", "austin evans", "dave2d",
    "justin whang", "internet historian", "wendigoon", "nexpo",
    "scare theater", "nightmind", "inside a mind", "nightmare expo",
    "jacksepticeye", "markiplier", "pewdiepie", "game grumps",
    "the game theorists", "matpat", "film theorists", "food theorists",
    "sidemen", "ksi", "simon", "jj", "vik", "harry", "ethan", "tobi",
    "logan paul", "jake paul", "impaulsive", "logan paul podcast",
]

# More politicians (expanded)
POLITICIANS_EXTENDED = [
    # More India
    "sharad pawar", "lalu prasad yadav", "mulayam singh",
    "chandrababu naidu", "jagan mohan reddy", "pinarayi vijayan",
    "stalin", "edappadi palaniswami", "devendra fadnavis",
    "shivraj singh chouhan", "vasundhara raje", "raghuram rajan",
    "manmohan singh", "atal bihari vajpayee", "indira gandhi",
    "rajiv gandhi", "nehru", "sardar patel",
    
    # More USA
    "nancy pelosi", "chuck schumer", "mitch mcconnell",
    "alexandria ocasio-cortez", "bernie sanders", "elizabeth warren",
    "pete buttigieg", "andrew yang", "amy klobuchar",
    
    # More international
    "angela merkel", "olaf scholz", "giorgia meloni",
    "recep erdogan", "benjamin netanyahu", "mohammed bin salman",
    "crown prince", "king", "queen", "prince", "princess",
    
    # Historical political figures
    "winston churchill", "franklin roosevelt", "abraham lincoln",
    "george washington", "thomas jefferson", "john f kennedy",
    "martin luther king", "nelson mandela", "mahatma gandhi",
    
    # Expand to 100+ politicians - Adding more
    # More Indian politicians
    "lal krishna advani", "murli manohar joshi", "sushma swaraj",
    "vasundhara raje", "shivraj singh chouhan", "raman singh",
    "raghuram rajan", "urjit patel", "shaktikanta das",
    "p chidambaram", "kapil sibal", "pawan kumar bansal",
    "lalu prasad yadav", "rabri devi", "tejashwi yadav",
    "mulayam singh yadav", "akilesh yadav", "dimple yadav",
    "mayawati", "kanshi ram", "chandrashekhar azad",
    "arvind kejriwal", "manish sisodia", "satyendar jain",
    "mamata banerjee", "abhishek banerjee", "derek o brien",
    "jagan mohan reddy", "ysr", "ys jagan",
    "chandrababu naidu", "nara lokesh", "nara chandrababu naidu",
    "pinarayi vijayan", "kodiyeri balakrishnan", "thomas isaac",
    "mk stalin", "udhayanidhi stalin", "durai murugan",
    "edappadi palaniswami", "o panneerselvam", "eps",
    "devendra fadnavis", "nitin gadkari", "prakash javadekar",
    "sushil kumar shinde", "prithviraj chavan", "ashok chavan",
    "vijay raut", "uddhav thackeray", "aditya thackeray",
    "raj thackeray", "sanjay raut", "anil deshmukh",
    
    # More USA politicians
    "nancy pelosi", "chuck schumer", "mitch mcconnell",
    "kevin mccarthy", "hakeem jeffries", "steve scalise",
    "alexandria ocasio-cortez", "bernie sanders", "elizabeth warren",
    "pete buttigieg", "andrew yang", "amy klobuchar",
    "cory booker", "kirsten gillibrand", "kamala harris",
    "gavin newsom", "ron desantis", "greg abbott",
    "glenn youngkin", "sarah huckabee sanders", "kristi noem",
    "ron paul", "rand paul", "mike lee", "josh hawley",
    "ted cruz", "marco rubio", "rick scott", "tim scott",
    
    # More international leaders
    "angela merkel", "olaf scholz", "frank-walter steinmeier",
    "giorgia meloni", "mario draghi", "giuseppe conte",
    "recep tayyip erdogan", "kilicdaroglu", "ekrem imamoglu",
    "benjamin netanyahu", "yair lapid", "benny gantz",
    "mohammed bin salman", "mohammed bin zayed", "sheikh khalifa",
    "crown prince", "king charles", "queen elizabeth",
    "prince william", "prince harry", "prince george",
    "emmanuel macron", "marine le pen", "jean-luc melenchon",
    "justin trudeau", "jagmeet singh", "andrew scheer",
    "scott morrison", "anthony albanese", "peter dutton",
    "jacinda ardern", "chris hipkins", "simon bridges",
    "shinzo abe", "fumio kishida", "yoshihide suga",
    "moon jae-in", "yoon suk-yeol", "lee jae-myung",
    "xi jinping", "li keqiang", "wang yi",
    "vladimir putin", "dmitry medvedev", "sergey lavrov",
    "luiz inacio lula da silva", "jair bolsonaro", "michel temer",
]

# Additional categories
WEAPONS = [
    "gun", "rifle", "pistol", "revolver", "shotgun",
    "knife", "sword", "machete", "dagger",
    "bomb", "grenade", "explosive", "dynamite",
    "weapon", "firearm", "ammunition", "bullet",
]

ILLEGAL_ACTIVITIES = [
    "theft", "robbery", "burglary", "stealing",
    "fraud", "scam", "money laundering",
    "human trafficking", "smuggling", "counterfeit",
]

# Age-related (for minor protection)
AGE_INDICATORS = [
    "years old", "year old", "yrs old", "yr old",
    "age", "aged", "aging",
    "minor", "underage", "juvenile",
    "school", "elementary", "middle school", "high school",
    "college", "university", "student",
]
