import { motion } from "framer-motion";
import {
  ArrowRight,
  ChevronDown,
  Gauge,
  Layers,
  MapPinned,
  ScanLine,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";
import OrbitVisual from "../components/landing/OrbitVisual";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";

const FEATURES = [
  {
    icon: MapPinned,
    title: "AOI Selection",
    description:
      "Define an area of interest and work with satellite imagery scoped precisely to it.",
  },
  {
    icon: Sparkles,
    title: "Deep Learning Super Resolution",
    description:
      "Reconstruct higher-resolution, analysis-ready imagery from medium-resolution inputs.",
  },
  {
    icon: Layers,
    title: "Geospatial Fidelity",
    description:
      "Preserve georeferencing and coordinate reference systems throughout the pipeline.",
  },
  {
    icon: Gauge,
    title: "Quantitative Evaluation",
    description: "Validate output quality with PSNR, SSIM, and LPIPS metrics.",
  },
];

const PIPELINE_STEPS = [
  "Select Imagery / AOI",
  "Preprocess",
  "AI Super-Resolution",
  "Evaluate & Export",
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-bg">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 lg:px-8">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg border border-accent/30 bg-accent-soft">
            <Sparkles className="size-4 text-accent" aria-hidden="true" />
          </div>
          <span className="font-display text-sm font-semibold text-text-primary">
            SRM Platform
          </span>
        </div>
        <Button as={Link} to="/dashboard" size="sm" variant="secondary">
          Open Dashboard
        </Button>
      </header>

      <section className="scan-grid-bg relative overflow-hidden px-6 pb-24 pt-16 lg:px-8 lg:pt-24">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mb-6 inline-flex items-center gap-2 rounded-full border border-border-strong bg-surface px-3 py-1 text-xs font-medium text-text-secondary"
          >
            <span className="size-1.5 rounded-full bg-accent" />
            Smart India Hackathon
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.05 }}
            className="font-display text-4xl font-semibold tracking-tight text-text-primary sm:text-5xl lg:text-6xl"
          >
            Deep Learning Based{" "}
            <span className="text-gradient-accent">Super Resolution Mapping</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="mx-auto mt-5 max-w-2xl text-base text-text-secondary sm:text-lg"
          >
            Turn medium-resolution satellite imagery into higher-resolution,
            analysis-ready data — while preserving geospatial accuracy end to end.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.15 }}
            className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row"
          >
            <Button as={Link} to="/process" size="lg" icon={ScanLine}>
              Start New Analysis
            </Button>
            <Button as={Link} to="/dashboard" size="lg" variant="secondary" icon={ArrowRight}>
              View Dashboard
            </Button>
          </motion.div>
        </div>

        <OrbitVisual />

        <motion.a
          href="#features"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, y: [0, 6, 0] }}
          transition={{ opacity: { duration: 0.6, delay: 0.6 }, y: { repeat: Infinity, duration: 1.8, ease: "easeInOut" } }}
          className="absolute bottom-6 left-1/2 flex -translate-x-1/2 items-center justify-center text-text-muted hover:text-accent"
          aria-label="Scroll to features"
        >
          <ChevronDown className="size-5" aria-hidden="true" />
        </motion.a>
      </section>

      <section id="features" className="mx-auto max-w-7xl px-6 pb-24 lg:px-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.4, delay: i * 0.08 }}
            >
              <Card interactive className="h-full">
                <div className="mb-3 flex size-10 items-center justify-center rounded-lg border border-accent/30 bg-accent-soft">
                  <feature.icon className="size-5 text-accent" aria-hidden="true" />
                </div>
                <h3 className="font-display text-sm font-semibold text-text-primary">
                  {feature.title}
                </h3>
                <p className="mt-1.5 text-sm text-text-secondary">{feature.description}</p>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="border-t border-border bg-bg-elevated px-6 py-16 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <h2 className="text-center font-display text-xl font-semibold text-text-primary">
            Pipeline
          </h2>
          <div className="relative mt-10 grid grid-cols-2 gap-6 sm:grid-cols-4">
            <motion.div
              initial={{ scaleX: 0 }}
              whileInView={{ scaleX: 1 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              style={{ transformOrigin: "left" }}
              className="absolute left-[12.5%] right-[12.5%] top-5 hidden h-px bg-border-strong sm:block"
              aria-hidden="true"
            />
            {PIPELINE_STEPS.map((step, i) => (
              <motion.div
                key={step}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className="relative z-10 flex flex-col items-center text-center"
              >
                <div className="flex size-10 items-center justify-center rounded-full border border-accent/30 bg-accent-soft font-display text-sm font-semibold text-accent">
                  {i + 1}
                </div>
                <p className="mt-3 text-sm text-text-secondary">{step}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <footer className="px-6 py-8 text-center text-xs text-text-muted lg:px-8">
        Built for Smart India Hackathon — Super Resolution Mapping from Satellite Imagery.
      </footer>
    </div>
  );
}
