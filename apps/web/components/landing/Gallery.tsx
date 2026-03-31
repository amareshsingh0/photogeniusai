"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";

const examples = [
  { image: "/images/example-1.jpg", title: "Fantasy Mode", category: "Creative", description: "Ethereal fairy with magical lighting" },
  { image: "/images/example-2.jpg", title: "Dramatic Portrait", category: "Realism", description: "Cinematic studio lighting effect" },
  { image: "/images/example-3.jpg", title: "Romantic Style", category: "Romantic", description: "Golden hour couple portrait" },
];

export default function Gallery() {
  return (
    <section className="relative py-24 px-4">
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            See the <span className="gradient-text">Magic</span>
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Real examples. Create your own in <Link href="/generate" className="text-primary hover:underline">Generate</Link> or view in <Link href="/gallery" className="text-primary hover:underline">Gallery</Link>.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {examples.map((example, index) => (
            <motion.div
              key={example.title}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.15 }}
              className="group relative"
            >
              <Link href="/generate" className="block">
                <div className="relative rounded-2xl overflow-hidden aspect-square">
                  <Image
                    src={example.image}
                    alt={example.title}
                    width={400}
                    height={400}
                    className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-background via-background/20 to-transparent opacity-60 group-hover:opacity-80 transition-opacity" />
                  <div className="absolute inset-0 p-6 flex flex-col justify-end">
                    <span className="text-xs font-medium px-2 py-1 rounded-full bg-primary/20 text-primary w-fit mb-2">
                      {example.category}
                    </span>
                    <h3 className="text-xl font-semibold mb-1">{example.title}</h3>
                    <p className="text-sm text-muted-foreground">{example.description}</p>
                  </div>
                  <div className="absolute inset-0 rounded-2xl border-2 border-transparent group-hover:border-primary/50 transition-colors" />
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
