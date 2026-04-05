/**
 * poster-templates.ts — 10 pre-built poster templates for PhotoGenius AI
 *
 * Each template provides:
 * - prompt_prefix: pre-filled prompt that gets passed to generate
 * - poster_design defaults: colors, font, layout
 * - ad_copy defaults: placeholder headline/cta/features
 * - recommended_ratio: suggested canvas size
 * - category: for filtering
 */

export interface PosterTemplate {
  id:            string
  name:          string
  emoji:         string
  category:      string
  description:   string
  prompt_prefix: string
  poster_design: {
    accent_color:         string
    bg_color:             string
    text_color_primary:   string
    text_color_secondary: string
    font_style:           string
    layout:               string
    has_feature_grid:     boolean
    has_cta_button:       boolean
    hero_occupies:        string
  }
  ad_copy: {
    headline:    string
    subheadline: string
    body:        string
    cta:         string
    tagline:     string
    features:    Array<{ icon: string; title: string; desc: string }>
  }
  recommended_ratio: '1:1' | '9:16' | '16:9' | '4:5'
  quality:           'balanced' | 'quality' | 'ultra'
  tags:              string[]
}

export const POSTER_TEMPLATES: PosterTemplate[] = [
  // ── 1. SaaS / App Launch ───────────────────────────────────────────────────
  {
    id:          'saas_launch',
    name:        'SaaS App Launch',
    emoji:       '🚀',
    category:    'Technology',
    description: 'Clean dark-themed poster for software product launches',
    prompt_prefix: 'Professional SaaS product launch poster, modern tech aesthetic, laptop showing clean dashboard UI on dark background',
    poster_design: {
      accent_color:         '#6366F1',
      bg_color:             '#0A0A1A',
      text_color_primary:   '#FFFFFF',
      text_color_secondary: '#A5B4FC',
      font_style:           'bold_tech',
      layout:               'hero_top_features_bottom',
      has_feature_grid:     true,
      has_cta_button:       true,
      hero_occupies:        'top_60',
    },
    ad_copy: {
      headline:    'NOW LIVE',
      subheadline: 'The AI platform that changes everything.',
      body:        'Automate your workflow with our cutting-edge AI tools.',
      cta:         'START FREE TRIAL',
      tagline:     'No credit card required · Free 14-day trial',
      features: [
        { icon: '⚡', title: 'Blazing Fast',    desc: '10x faster than competitors' },
        { icon: '🤖', title: 'AI Powered',      desc: 'Smart automation built-in' },
        { icon: '🔒', title: 'Enterprise Safe', desc: 'SOC 2 Type II certified' },
        { icon: '📊', title: 'Analytics',       desc: 'Real-time insights dashboard' },
      ],
    },
    recommended_ratio: '9:16',
    quality:           'quality',
    tags: ['saas', 'tech', 'launch', 'app', 'software'],
  },

  // ── 2. Diwali Festival Sale ────────────────────────────────────────────────
  {
    id:          'diwali_sale',
    name:        'Diwali Festival Sale',
    emoji:       '🪔',
    category:    'Festival',
    description: 'Warm festive Diwali sale poster with diyas and lights',
    prompt_prefix: 'Diwali festival sale poster, warm golden diyas and rangoli, bokeh lights, festive Indian celebration atmosphere',
    poster_design: {
      accent_color:         '#FFD700',
      bg_color:             '#1A0800',
      text_color_primary:   '#FFFFFF',
      text_color_secondary: '#FFD700',
      font_style:           'expressive_display',
      layout:               'hero_top_features_bottom',
      has_feature_grid:     false,
      has_cta_button:       true,
      hero_occupies:        'top_60',
    },
    ad_copy: {
      headline:    'DIWALI SALE',
      subheadline: 'Up to 50% off on everything',
      body:        'Celebrate the festival of lights with unbeatable deals.',
      cta:         'SHOP NOW',
      tagline:     'Offer valid till Diwali midnight',
      features: [
        { icon: '🪔', title: '50% Off',        desc: 'On all premium products' },
        { icon: '🚚', title: 'Free Delivery',  desc: 'Orders above ₹499' },
        { icon: '🎁', title: 'Festive Gifts',  desc: 'With every order' },
        { icon: '⚡', title: 'Flash Deals',    desc: 'Every hour, all day' },
      ],
    },
    recommended_ratio: '1:1',
    quality:           'quality',
    tags: ['diwali', 'festival', 'sale', 'india', 'offer'],
  },

  // ── 3. Restaurant / Food ───────────────────────────────────────────────────
  {
    id:          'food_restaurant',
    name:        'Food & Restaurant',
    emoji:       '🍽️',
    category:    'Food',
    description: 'Appetizing food photo poster for restaurants and cafes',
    prompt_prefix: 'Luxury restaurant food poster, hero product shot with appetizing food, warm professional lighting, bokeh background, Michelin star quality plating',
    poster_design: {
      accent_color:         '#F97316',
      bg_color:             '#1A0800',
      text_color_primary:   '#FFFFFF',
      text_color_secondary: '#FED7AA',
      font_style:           'elegant_serif',
      layout:               'hero_top_features_bottom',
      has_feature_grid:     false,
      has_cta_button:       true,
      hero_occupies:        'top_60',
    },
    ad_copy: {
      headline:    'TASTE PERFECTION',
      subheadline: 'Authentic flavors, crafted with love.',
      body:        'Reserve your table for an unforgettable dining experience.',
      cta:         'BOOK TABLE',
      tagline:     'Open daily 12pm – 11pm',
      features: [
        { icon: '👨‍🍳', title: 'Master Chef',   desc: 'Award-winning cuisine' },
        { icon: '🌿', title: 'Farm Fresh',     desc: '100% organic ingredients' },
        { icon: '🍷', title: 'Wine Pairing',   desc: 'Curated selection' },
        { icon: '⭐', title: 'Top Rated',      desc: '4.9 on Google & Zomato' },
      ],
    },
    recommended_ratio: '4:5',
    quality:           'quality',
    tags: ['food', 'restaurant', 'cafe', 'dining', 'menu'],
  },

  // ── 4. Fashion Editorial ───────────────────────────────────────────────────
  {
    id:          'fashion_editorial',
    name:        'Fashion Editorial',
    emoji:       '👗',
    category:    'Fashion',
    description: 'High-fashion editorial poster for clothing brands',
    prompt_prefix: 'High fashion editorial poster, model wearing premium clothing, Vogue magazine aesthetic, dramatic studio lighting, minimalist dark background',
    poster_design: {
      accent_color:         '#F472B6',
      bg_color:             '#0F0010',
      text_color_primary:   '#FFFFFF',
      text_color_secondary: '#F9A8D4',
      font_style:           'elegant_serif',
      layout:               'split_left_right',
      has_feature_grid:     false,
      has_cta_button:       true,
      hero_occupies:        'left_half',
    },
    ad_copy: {
      headline:    'NEW SEASON',
      subheadline: 'Fall/Winter 2025 Collection',
      body:        'Redefine your style with our latest collection.',
      cta:         'EXPLORE NOW',
      tagline:     'Free returns · Express delivery',
      features: [
        { icon: '✨', title: 'Luxury',       desc: 'Premium quality fabrics' },
        { icon: '🌍', title: 'Sustainable',  desc: 'Ethically sourced' },
        { icon: '📦', title: 'Fast Ship',    desc: 'Next-day delivery' },
        { icon: '↩️', title: 'Easy Returns', desc: 'Hassle-free 30 days' },
      ],
    },
    recommended_ratio: '9:16',
    quality:           'ultra',
    tags: ['fashion', 'clothing', 'collection', 'editorial', 'style'],
  },

  // ── 5. Fitness / Gym ──────────────────────────────────────────────────────
  {
    id:          'fitness_gym',
    name:        'Fitness & Gym',
    emoji:       '💪',
    category:    'Health & Fitness',
    description: 'High-energy gym and fitness promotional poster',
    prompt_prefix: 'Dynamic fitness gym promotional poster, athlete in action with dramatic lighting, energy and power, dark background with cinematic lighting',
    poster_design: {
      accent_color:         '#EF4444',
      bg_color:             '#0F0000',
      text_color_primary:   '#FFFFFF',
      text_color_secondary: '#FCA5A5',
      font_style:           'bold_tech',
      layout:               'hero_top_features_bottom',
      has_feature_grid:     true,
      has_cta_button:       true,
      hero_occupies:        'top_60',
    },
    ad_copy: {
      headline:    'LEVEL UP',
      subheadline: 'Transform your body in 90 days.',
      body:        'Join thousands who have already changed their lives.',
      cta:         'JOIN NOW',
      tagline:     'First month free · Cancel anytime',
      features: [
        { icon: '🏋️', title: 'Equipment',    desc: '200+ premium machines' },
        { icon: '👥', title: 'Coaches',       desc: 'Certified personal trainers' },
        { icon: '🥗', title: 'Nutrition',     desc: 'Custom diet plans' },
        { icon: '📱', title: 'App Access',    desc: 'Track workouts anywhere' },
      ],
    },
    recommended_ratio: '1:1',
    quality:           'quality',
    tags: ['fitness', 'gym', 'health', 'workout', 'sports'],
  },

  // ── 6. Real Estate ────────────────────────────────────────────────────────
  {
    id:          'real_estate',
    name:        'Real Estate Property',
    emoji:       '🏠',
    category:    'Real Estate',
    description: 'Luxurious real estate listing poster',
    prompt_prefix: 'Luxury real estate property poster, modern architecture exterior shot, golden hour lighting, premium residential development',
    poster_design: {
      accent_color:         '#C9A84C',
      bg_color:             '#0A1A10',
      text_color_primary:   '#FFFFFF',
      text_color_secondary: '#C9A84C',
      font_style:           'elegant_serif',
      layout:               'hero_top_features_bottom',
      has_feature_grid:     true,
      has_cta_button:       true,
      hero_occupies:        'top_60',
    },
    ad_copy: {
      headline:    'DREAM HOME',
      subheadline: 'Exclusive luxury villas from ₹2.5 Cr',
      body:        'Live where luxury meets nature in our gated community.',
      cta:         'SCHEDULE VISIT',
      tagline:     'RERA Approved · Ready to Move',
      features: [
        { icon: '🏊', title: 'Amenities',    desc: 'Pool, gym, clubhouse' },
        { icon: '🌳', title: 'Green Zone',   desc: '40% open landscaping' },
        { icon: '🔐', title: '24/7 Security', desc: 'Smart CCTV + guards' },
        { icon: '📍', title: 'Location',     desc: '5 min from highway' },
      ],
    },
    recommended_ratio: '4:5',
    quality:           'quality',
    tags: ['real_estate', 'property', 'home', 'luxury', 'apartment'],
  },

  // ── 7. Event / Concert ────────────────────────────────────────────────────
  {
    id:          'event_concert',
    name:        'Event & Concert',
    emoji:       '🎵',
    category:    'Entertainment',
    description: 'Bold event and concert promotional poster',
    prompt_prefix: 'Electric concert event promotional poster, stage lights and crowd energy, dramatic neon lighting, music festival atmosphere',
    poster_design: {
      accent_color:         '#A855F7',
      bg_color:             '#0A0010',
      text_color_primary:   '#FFFFFF',
      text_color_secondary: '#C4B5FD',
      font_style:           'expressive_display',
      layout:               'centered_minimal',
      has_feature_grid:     false,
      has_cta_button:       true,
      hero_occupies:        'top_60',
    },
    ad_copy: {
      headline:    'LIVE TONIGHT',
      subheadline: 'The biggest night of the year',
      body:        'Join 10,000+ fans for an unforgettable night.',
      cta:         'BUY TICKETS',
      tagline:     'Limited seats · VIP packages available',
      features: [
        { icon: '🎤', title: 'Live Artists', desc: '20+ performers' },
        { icon: '🎪', title: 'Venue',         desc: 'Open air arena' },
        { icon: '🍹', title: 'Food & Bar',    desc: 'Premium F&B zone' },
        { icon: '🎟️', title: 'Passes',       desc: 'Day / Weekend / VIP' },
      ],
    },
    recommended_ratio: '9:16',
    quality:           'quality',
    tags: ['event', 'concert', 'music', 'festival', 'ticket'],
  },

  // ── 8. E-commerce / Product Sale ──────────────────────────────────────────
  {
    id:          'ecommerce_sale',
    name:        'E-Commerce Sale',
    emoji:       '🛍️',
    category:    'Retail',
    description: 'High-urgency e-commerce sale and discount poster',
    prompt_prefix: 'E-commerce big sale promotional poster, product showcase with vibrant energy, shopping bags and discount tags, modern retail aesthetic',
    poster_design: {
      accent_color:         '#EF4444',
      bg_color:             '#150000',
      text_color_primary:   '#FFFFFF',
      text_color_secondary: '#FCA5A5',
      font_style:           'bold_tech',
      layout:               'hero_top_features_bottom',
      has_feature_grid:     false,
      has_cta_button:       true,
      hero_occupies:        'top_55',
    },
    ad_copy: {
      headline:    '70% OFF',
      subheadline: 'Mega End of Season Sale — Today Only',
      body:        'Shop thousands of deals before they run out.',
      cta:         'SHOP SALE',
      tagline:     'Use code MEGA70 · Free shipping above ₹599',
      features: [
        { icon: '🔥', title: 'Flash Sale',    desc: 'Ends in 24 hours' },
        { icon: '🎁', title: 'Free Gift',     desc: 'On orders ₹1000+' },
        { icon: '💳', title: 'EMI Options',   desc: 'No cost EMI available' },
        { icon: '↩️', title: 'Easy Return',  desc: '30-day no-questions' },
      ],
    },
    recommended_ratio: '1:1',
    quality:           'quality',
    tags: ['ecommerce', 'sale', 'discount', 'shopping', 'offer'],
  },

  // ── 9. App Download / Mobile ───────────────────────────────────────────────
  {
    id:          'app_download',
    name:        'App Download',
    emoji:       '📱',
    category:    'Technology',
    description: 'Mobile app download poster for Play Store / App Store',
    prompt_prefix: 'Mobile app download promotional poster, phone mockup showing clean app UI, modern tech aesthetic, dark background with app store badges',
    poster_design: {
      accent_color:         '#10B981',
      bg_color:             '#0A1A12',
      text_color_primary:   '#FFFFFF',
      text_color_secondary: '#6EE7B7',
      font_style:           'clean_sans',
      layout:               'hero_top_features_bottom',
      has_feature_grid:     true,
      has_cta_button:       true,
      hero_occupies:        'top_60',
    },
    ad_copy: {
      headline:    'DOWNLOAD NOW',
      subheadline: '500K+ happy users and counting',
      body:        'Available on iOS and Android — completely free.',
      cta:         'GET THE APP',
      tagline:     'Rated 4.8 ★ on App Store & Play Store',
      features: [
        { icon: '⚡', title: 'Instant',      desc: 'Works offline too' },
        { icon: '🔒', title: 'Secure',       desc: 'Bank-grade encryption' },
        { icon: '🆓', title: 'Free Forever', desc: 'Core features always free' },
        { icon: '🌐', title: 'Cross-Platform', desc: 'iOS, Android, Web' },
      ],
    },
    recommended_ratio: '9:16',
    quality:           'balanced',
    tags: ['app', 'mobile', 'download', 'ios', 'android'],
  },

  // ── 10. Corporate B2B ─────────────────────────────────────────────────────
  {
    id:          'corporate_b2b',
    name:        'Corporate / B2B',
    emoji:       '💼',
    category:    'Business',
    description: 'Professional corporate poster for B2B brands and services',
    prompt_prefix: 'Professional corporate business poster, modern office environment with team collaboration, clean professional aesthetic, trust and reliability',
    poster_design: {
      accent_color:         '#3B82F6',
      bg_color:             '#0A1020',
      text_color_primary:   '#FFFFFF',
      text_color_secondary: '#93C5FD',
      font_style:           'clean_sans',
      layout:               'hero_top_features_bottom',
      has_feature_grid:     true,
      has_cta_button:       true,
      hero_occupies:        'top_55',
    },
    ad_copy: {
      headline:    'GROW FASTER',
      subheadline: 'Enterprise solutions built for scale.',
      body:        'Trusted by 5000+ companies across 40 countries.',
      cta:         'BOOK DEMO',
      tagline:     'SOC 2 · ISO 27001 · GDPR Compliant',
      features: [
        { icon: '📈', title: 'Revenue',      desc: 'Avg 2.3x revenue growth' },
        { icon: '⏱️', title: 'Time Saved',  desc: '40% ops cost reduction' },
        { icon: '🤝', title: 'Support',      desc: '24/7 dedicated team' },
        { icon: '🔗', title: 'Integrations', desc: '200+ native connectors' },
      ],
    },
    recommended_ratio: '16:9',
    quality:           'quality',
    tags: ['corporate', 'b2b', 'enterprise', 'business', 'professional'],
  },
]

// ── Helpers ────────────────────────────────────────────────────────────────────

export function getTemplateById(id: string): PosterTemplate | undefined {
  return POSTER_TEMPLATES.find(t => t.id === id)
}

export function getTemplatesByCategory(category: string): PosterTemplate[] {
  if (category === 'All') return POSTER_TEMPLATES
  return POSTER_TEMPLATES.filter(t => t.category === category)
}

export const TEMPLATE_CATEGORIES = [
  'All',
  ...Array.from(new Set(POSTER_TEMPLATES.map(t => t.category))),
]
