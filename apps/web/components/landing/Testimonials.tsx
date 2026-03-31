"use client";

import { motion } from "framer-motion";
import { Star, Quote } from "lucide-react";
import Image from "next/image";

const testimonials = [
  {
    id: 1,
    name: "Sarah Chen",
    role: "Professional Photographer",
    avatar: "https://api.dicebear.com/7.x/avataaars/svg?seed=Sarah",
    rating: 5,
    text: "PhotoGenius AI has revolutionized my workflow. The quality is incredible and the safety features give me peace of mind.",
  },
  {
    id: 2,
    name: "Michael Rodriguez",
    role: "Content Creator",
    avatar: "https://api.dicebear.com/7.x/avataaars/svg?seed=Michael",
    rating: 5,
    text: "The instant preview feature is a game-changer. I can iterate quickly and get exactly what I need in minutes.",
  },
  {
    id: 3,
    name: "Emily Watson",
    role: "Marketing Director",
    avatar: "https://api.dicebear.com/7.x/avataaars/svg?seed=Emily",
    rating: 5,
    text: "Best-of-N selection means I always get the perfect shot. The quality scores help me make informed decisions.",
  },
  {
    id: 4,
    name: "David Kim",
    role: "Freelance Designer",
    avatar: "https://api.dicebear.com/7.x/avataaars/svg?seed=David",
    rating: 5,
    text: "The romantic presets are perfect for my client work. Professional quality with creative flexibility.",
  },
];

export default function Testimonials() {
  return (
    <section className="relative py-24 px-4 overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-primary/10 blur-3xl" />
      </div>

      <div className="relative max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            Loved by <span className="gradient-text">Creators</span>
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            See what our users are saying about PhotoGenius AI
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {testimonials.map((testimonial, index) => (
            <motion.div
              key={testimonial.id}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              className="glass-card rounded-2xl p-6 hover:border-primary/50 transition-all"
            >
              <div className="flex items-start space-x-4 mb-4">
                <div className="relative h-12 w-12 rounded-full overflow-hidden flex-shrink-0 border border-border/50">
                  <Image
                    src={testimonial.avatar}
                    alt={testimonial.name}
                    fill
                    className="object-cover"
                    unoptimized
                  />
                </div>
                <div className="flex-1">
                  <h4 className="font-semibold text-foreground mb-1">
                    {testimonial.name}
                  </h4>
                  <p className="text-sm text-muted-foreground mb-2">
                    {testimonial.role}
                  </p>
                  <div className="flex items-center space-x-1">
                    {Array.from({ length: testimonial.rating }).map((_, i) => (
                      <Star
                        key={i}
                        className="h-4 w-4 text-primary fill-current"
                      />
                    ))}
                  </div>
                </div>
                <Quote className="h-6 w-6 text-primary/30 flex-shrink-0" />
              </div>
              <p className="text-muted-foreground leading-relaxed">
                &ldquo;{testimonial.text}&rdquo;
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
