# Frontend

This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

Let me know if the resolution isn't high enough or if you have any questions. You pretty much have free reign. This repo was largely generated in AntiGravity with no human touch or intervention.

Please create a feature branch for your work and create tags for working versions. Merge back into master, but we just want to ensure that there are tags for ``artesinal'' code made with human TLC because the high-quality human-written code might be accidentally overwritten by vibe coding.

### Development Mode

First, run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `src/app/page.tsx`. The page auto-updates as you edit the file.

### Docker

This project is fully dockerized for deployment to Kubernetes.

#### Build the Docker image:

```bash
# Build the Docker image
docker build -t frontend:latest .

# Run the container locally for testing
docker run -p 3000:3000 frontend:latest
```

The application will be available at [http://localhost:3000](http://localhost:3000).

#### Kubernetes Deployment

This project is designed to be deployed to Kubernetes with Flux for GitOps-based continuous delivery. The Dockerfile uses multi-stage builds and Next.js standalone output for optimal image size and performance.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

## Tasklist
 - [ ] Master back-end integrations by defining a standard JSON structure for data received from backend variant callers and annotation software
 - [ ] Represent data graphically on the frontend
 - [ ] Implement login and authentification
 - [ ] Local VCF processing
 - [ ] Ensure that no identifying information regarding the genotype of the user is being sent to the backend

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

