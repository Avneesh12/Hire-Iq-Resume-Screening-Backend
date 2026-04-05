"""
Resume Dataset Generator
Generates a large synthetic resume dataset for training a resume screening model.
Run this script first to generate 'resume_dataset.csv'
"""

import csv
import random

random.seed(42)

# ─────────────────────────────────────────────
# SKILL POOLS PER CATEGORY
# ─────────────────────────────────────────────

CATEGORIES = {
    "machine_learning": {
        "skills": [
            "python", "tensorflow", "pytorch", "scikit-learn", "keras", "numpy", "pandas",
            "matplotlib", "seaborn", "xgboost", "lightgbm", "catboost", "huggingface",
            "transformers", "bert", "gpt", "nlp", "computer vision", "opencv", "deep learning",
            "neural networks", "cnn", "rnn", "lstm", "attention mechanism", "reinforcement learning",
            "feature engineering", "model deployment", "mlflow", "wandb", "jupyter", "colab",
            "data augmentation", "transfer learning", "fine tuning", "hyperparameter tuning",
            "cross validation", "gradient descent", "backpropagation", "regression", "classification",
            "clustering", "dimensionality reduction", "pca", "tsne", "umap", "automl", "bayesian optimization"
        ],
        "job_titles": [
            "Machine Learning Engineer", "Data Scientist", "AI Engineer", "NLP Engineer",
            "Computer Vision Engineer", "Research Scientist", "MLOps Engineer", "Deep Learning Engineer"
        ],
        "education": [
            "B.Tech Computer Science", "M.Tech Artificial Intelligence", "PhD Machine Learning",
            "B.Sc Statistics", "M.Sc Data Science", "B.Tech Electronics"
        ]
    },
    "backend": {
        "skills": [
            "java", "spring boot", "spring framework", "hibernate", "jpa", "python", "django",
            "flask", "fastapi", "node.js", "express.js", "go", "golang", "rust", "c#", ".net",
            "asp.net", "ruby", "ruby on rails", "php", "laravel", "rest api", "graphql", "grpc",
            "microservices", "docker", "kubernetes", "aws", "azure", "gcp", "postgresql", "mysql",
            "mongodb", "redis", "rabbitmq", "kafka", "celery", "nginx", "apache", "linux", "bash",
            "ci/cd", "jenkins", "github actions", "terraform", "ansible", "jwt", "oauth",
            "api gateway", "load balancer", "caching", "message queue", "sql", "nosql"
        ],
        "job_titles": [
            "Backend Developer", "Software Engineer", "API Developer", "Java Developer",
            "Python Developer", "Node.js Developer", "Cloud Engineer", "DevOps Engineer",
            "Site Reliability Engineer", "Platform Engineer"
        ],
        "education": [
            "B.Tech Computer Science", "B.E Software Engineering", "M.Tech Computer Science",
            "B.Sc Computer Science", "MCA", "B.Tech Information Technology"
        ]
    },
    "frontend": {
        "skills": [
            "html", "css", "javascript", "typescript", "react", "next.js", "vue.js", "nuxt.js",
            "angular", "svelte", "tailwind css", "bootstrap", "sass", "scss", "less",
            "webpack", "vite", "rollup", "babel", "eslint", "prettier", "jest", "cypress",
            "react testing library", "storybook", "figma", "adobe xd", "responsive design",
            "web accessibility", "wcag", "seo", "performance optimization", "lazy loading",
            "code splitting", "progressive web app", "service worker", "graphql", "apollo",
            "redux", "zustand", "context api", "react query", "axios", "fetch api",
            "websockets", "three.js", "d3.js", "framer motion", "gsap", "animation"
        ],
        "job_titles": [
            "Frontend Developer", "React Developer", "UI Developer", "Web Developer",
            "Angular Developer", "Vue.js Developer", "UI/UX Developer", "JavaScript Developer"
        ],
        "education": [
            "B.Tech Computer Science", "B.Sc Computer Science", "BCA", "B.Tech Information Technology",
            "Diploma in Web Development", "B.E Computer Engineering"
        ]
    },
    "data_engineering": {
        "skills": [
            "apache spark", "hadoop", "hive", "pig", "kafka", "airflow", "luigi", "prefect",
            "dbt", "snowflake", "redshift", "bigquery", "databricks", "delta lake", "iceberg",
            "python", "scala", "java", "sql", "nosql", "etl", "elt", "data pipeline",
            "data warehouse", "data lake", "data lakehouse", "parquet", "avro", "orc",
            "elasticsearch", "kibana", "logstash", "fluentd", "flink", "beam", "nifi",
            "glue", "emr", "hdfs", "s3", "azure data factory", "synapse", "power bi",
            "tableau", "looker", "metabase", "data modeling", "star schema", "data quality"
        ],
        "job_titles": [
            "Data Engineer", "Big Data Engineer", "ETL Developer", "Data Platform Engineer",
            "Analytics Engineer", "Data Architect", "Pipeline Engineer"
        ],
        "education": [
            "B.Tech Computer Science", "M.Tech Data Engineering", "B.Sc Statistics",
            "M.Sc Computer Science", "B.Tech Information Technology", "MBA Analytics"
        ]
    },
    "cybersecurity": {
        "skills": [
            "penetration testing", "ethical hacking", "vulnerability assessment", "kali linux",
            "metasploit", "nmap", "burp suite", "wireshark", "owasp", "web application security",
            "network security", "firewall", "ids", "ips", "siem", "splunk", "qradar",
            "incident response", "digital forensics", "malware analysis", "reverse engineering",
            "cryptography", "pki", "ssl", "tls", "vpn", "zero trust", "soc", "threat intelligence",
            "risk assessment", "compliance", "iso 27001", "nist", "gdpr", "hipaa",
            "python scripting", "bash scripting", "powershell", "active directory", "ldap",
            "cloud security", "aws security", "azure security", "devsecops", "soar", "ctf"
        ],
        "job_titles": [
            "Cybersecurity Analyst", "Security Engineer", "Penetration Tester", "SOC Analyst",
            "Information Security Engineer", "Cloud Security Engineer", "Security Architect"
        ],
        "education": [
            "B.Tech Computer Science", "B.Sc Cybersecurity", "M.Tech Information Security",
            "B.E Electronics", "Certified Ethical Hacker (CEH)", "CISSP"
        ]
    },
    "mobile": {
        "skills": [
            "android", "ios", "kotlin", "java", "swift", "objective-c", "react native",
            "flutter", "dart", "xamarin", "ionic", "capacitor", "expo", "android studio",
            "xcode", "firebase", "realm", "sqlite", "room database", "core data",
            "retrofit", "okhttp", "alamofire", "mvvm", "mvc", "clean architecture",
            "jetpack compose", "swiftui", "uikit", "material design", "push notifications",
            "fcm", "apns", "google play", "app store", "gradle", "cocoapods", "spm",
            "unit testing", "ui testing", "espresso", "xctest", "fastlane", "ci/cd mobile"
        ],
        "job_titles": [
            "Android Developer", "iOS Developer", "Mobile Developer", "Flutter Developer",
            "React Native Developer", "Cross-Platform Developer"
        ],
        "education": [
            "B.Tech Computer Science", "B.Sc Computer Science", "BCA", "MCA",
            "B.Tech Information Technology", "Diploma Mobile Development"
        ]
    },
    "devops": {
        "skills": [
            "docker", "kubernetes", "helm", "istio", "terraform", "ansible", "puppet", "chef",
            "jenkins", "gitlab ci", "github actions", "circleci", "argocd", "flux", "gitops",
            "aws", "azure", "gcp", "linux", "bash", "python", "go", "prometheus", "grafana",
            "elk stack", "loki", "jaeger", "opentelemetry", "nginx", "haproxy", "traefik",
            "vault", "consul", "service mesh", "infrastructure as code", "configuration management",
            "monitoring", "alerting", "logging", "tracing", "sre", "sla", "slo", "sli",
            "disaster recovery", "high availability", "autoscaling", "load balancing"
        ],
        "job_titles": [
            "DevOps Engineer", "Cloud Engineer", "Infrastructure Engineer", "SRE",
            "Platform Engineer", "Kubernetes Engineer", "CI/CD Engineer"
        ],
        "education": [
            "B.Tech Computer Science", "B.E Electronics", "M.Tech Computer Science",
            "B.Sc Information Technology", "AWS Certified", "CKA Certified"
        ]
    },
    "fullstack": {
        "skills": [
            "react", "node.js", "express.js", "mongodb", "postgresql", "mysql", "typescript",
            "javascript", "html", "css", "tailwind css", "next.js", "graphql", "rest api",
            "docker", "aws", "nginx", "redis", "jwt", "oauth", "git", "github", "agile",
            "python", "django", "flask", "vue.js", "angular", "webpack", "vite",
            "jest", "cypress", "ci/cd", "linux", "bash", "microservices", "websockets",
            "stripe api", "payment integration", "elasticsearch", "meilisearch"
        ],
        "job_titles": [
            "Full Stack Developer", "MEAN Stack Developer", "MERN Stack Developer",
            "Software Engineer", "Web Developer", "Product Engineer"
        ],
        "education": [
            "B.Tech Computer Science", "B.Sc Computer Science", "BCA", "MCA",
            "B.Tech Software Engineering", "B.E Computer Engineering"
        ]
    }
}

EXPERIENCE_TEMPLATES = [
    "Developed and maintained {skill1} applications using {skill2} and {skill3}.",
    "Implemented {skill1} solutions to improve system performance by 40%.",
    "Built scalable {skill1} pipelines with {skill2} achieving 99.9% uptime.",
    "Led a team of 5 engineers to deliver {skill1} projects on time.",
    "Designed and deployed {skill1} infrastructure using {skill2}.",
    "Optimized {skill1} workflows reducing latency by 60% using {skill2}.",
    "Integrated {skill1} with {skill2} for seamless data flow.",
    "Contributed to open-source {skill1} projects on GitHub.",
    "Collaborated with cross-functional teams on {skill1} and {skill2} solutions.",
    "Migrated legacy systems to modern {skill1} architecture using {skill2}.",
    "Automated {skill1} processes saving 20 hours of manual work weekly.",
    "Wrote unit tests and integration tests for {skill1} modules.",
    "Conducted code reviews for {skill1} and {skill2} implementations.",
    "Published research paper on {skill1} optimization techniques.",
    "Achieved {skill1} certification and applied it in production environments."
]

COMPANIES = [
    "TechCorp India", "Infosys", "TCS", "Wipro", "HCL Technologies",
    "Cognizant", "Accenture", "IBM India", "Microsoft India", "Google India",
    "Amazon India", "Flipkart", "Zomato", "Ola", "Paytm", "Razorpay",
    "Freshworks", "Zoho", "MakeMyTrip", "Swiggy", "BYJU's", "Unacademy",
    "InMobi", "Mu Sigma", "Fractal Analytics", "Tiger Analytics", "Sigmoid"
]


def generate_resume_text(category_name, category_data):
    skills = category_data["skills"]
    titles = category_data["job_titles"]
    educations = category_data["education"]

    # Pick random subset of skills (8-18 skills)
    chosen_skills = random.sample(skills, min(random.randint(8, 18), len(skills)))

    # Pick random title and education
    title = random.choice(titles)
    edu = random.choice(educations)
    company = random.choice(COMPANIES)
    years = random.randint(1, 10)

    # Generate 3-5 experience lines
    exp_lines = []
    for _ in range(random.randint(3, 5)):
        template = random.choice(EXPERIENCE_TEMPLATES)
        s1 = random.choice(chosen_skills)
        s2 = random.choice(chosen_skills)
        s3 = random.choice(chosen_skills)
        exp_lines.append(template.format(skill1=s1, skill2=s2, skill3=s3))

    resume_parts = [
        f"Job Title: {title}",
        f"Education: {edu}",
        f"Experience: {years} years at {company}",
        f"Skills: {', '.join(chosen_skills)}",
        "Summary: " + " ".join(exp_lines)
    ]

    return " | ".join(resume_parts)


def generate_dataset(total_samples=2000):
    data = []
    categories = list(CATEGORIES.keys())
    samples_per_category = total_samples // len(categories)

    for category_name, category_data in CATEGORIES.items():
        for _ in range(samples_per_category):
            text = generate_resume_text(category_name, category_data)
            data.append({"text": text, "label": category_name})

    random.shuffle(data)
    return data


if __name__ == "__main__":
    print("⏳ Generating dataset...")
    dataset = generate_dataset(total_samples=2000)

    with open("ml_/datasets/resume_dataset.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label"])
        writer.writeheader()
        writer.writerows(dataset)

    print(f"✅ Dataset generated: {len(dataset)} samples → resume_dataset.csv")

    # Distribution
    from collections import Counter
    counts = Counter(d["label"] for d in dataset)
    print("\n📊 Label Distribution:")
    for label, count in sorted(counts.items()):
        print(f"  {label:25s}: {count} samples")
