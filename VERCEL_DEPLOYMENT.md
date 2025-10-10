# Vercel Deployment Guide for Mitra Bot

This guide will help you deploy your Mitra Bot application to Vercel.

## Prerequisites

1. A Vercel account (sign up at https://vercel.com)
2. Your GitHub repository connected to Vercel
3. PostgreSQL database (recommended: Vercel Postgres, Neon, or Supabase)

## Step 1: Set Up PostgreSQL Database

### Option A: Vercel Postgres (Recommended)

1. Go to your Vercel dashboard
2. Select your project
3. Go to "Storage" tab
4. Click "Create Database"
5. Select "Postgres"
6. Copy the `DATABASE_URL` provided

### Option B: Neon (Free PostgreSQL)

1. Sign up at https://neon.tech
2. Create a new project
3. Copy the connection string (looks like: `postgresql://user:pass@host.neon.tech/dbname`)

### Option C: Supabase

1. Sign up at https://supabase.com
2. Create a new project
3. Go to Settings > Database
4. Copy the connection string

## Step 2: Configure Environment Variables in Vercel

1. Go to your Vercel project dashboard
2. Click on "Settings" tab
3. Click on "Environment Variables"
4. Add the following variables:

```bash
# Required Variables
DATABASE_URL=postgresql://user:password@host:5432/database
OPENAI_API_KEY=sk-your-openai-api-key-here
JWT_SECRET_KEY=your-random-secret-key-here
SECRET_KEY=your-random-secret-key-here

# Optional Variables (with defaults)
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_TEMPERATURE=0.7
MAX_RESPONSE_TOKENS=500
FLASK_ENV=production
PASSWORD_MIN_LENGTH=8
ALLOWED_ORIGINS=*
MAX_FILE_SIZE=16777216
LOG_LEVEL=INFO
DB_ECHO=false
```

### How to Generate Secret Keys

Run this in Python to generate secure random keys:

```python
import secrets
print(secrets.token_urlsafe(32))
```

## Step 3: Push Files to GitHub

Make sure these files are in your repository:

```bash
git add .
git commit -m "Configure for Vercel deployment"
git push origin main
```

Required files:
- ✅ `runtime.txt` (Python 3.11)
- ✅ `vercel.json` (Vercel configuration)
- ✅ `api/index.py` (Serverless entry point)
- ✅ `requirements.txt` (Python dependencies)
- ✅ `.env.example` (Environment variable template)

## Step 4: Deploy to Vercel

### Method 1: Automatic Deployment (Recommended)

1. Go to https://vercel.com/new
2. Import your GitHub repository
3. Vercel will auto-detect the configuration
4. Click "Deploy"

### Method 2: Using Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Login to Vercel
vercel login

# Deploy
vercel
```

## Step 5: Initialize Database

After deployment, you need to create database tables. You have two options:

### Option A: Using Vercel CLI

```bash
# Connect to your deployment
vercel env pull .env.production

# Run database migrations (if you have them)
# Or connect to your database and run SQL
```

### Option B: Direct Database Connection

Connect to your PostgreSQL database using a client (pgAdmin, psql, or DBeaver) and run:

```sql
-- The tables will be auto-created when the app first runs
-- But you can manually create them if needed
```

The app will auto-create tables on first request due to this line in app.py:
```python
Base.metadata.create_all(engine)
```

## Step 6: Test Your Deployment

1. Visit your Vercel URL (e.g., `https://your-app.vercel.app`)
2. Test the health endpoint: `https://your-app.vercel.app/api/health`
3. Try uploading a document
4. Test the chat functionality

## Important Notes for Vercel Serverless

### Limitations

1. **No persistent local storage**: Files uploaded are temporary
2. **Cold starts**: First request may be slow
3. **Execution time limit**: 10 seconds for Hobby, 60s for Pro
4. **Memory limits**: 1GB for Hobby, 3GB for Pro

### Recommendations

1. **Use PostgreSQL** instead of SQLite (SQLite doesn't persist on Vercel)
2. **Store files externally**: Use AWS S3, Cloudinary, or Vercel Blob for file storage
3. **Optimize imports**: Only import what you need to reduce cold start time
4. **Use caching**: Consider Redis for session data (Vercel KV)

## Troubleshooting

### Build Fails with "distutils" Error

✅ Fixed by `runtime.txt` specifying Python 3.11

### "Application Error" on Deployed Site

1. Check Vercel logs: `vercel logs`
2. Verify environment variables are set correctly
3. Check database connection string

### Slow Response Times

This is normal for serverless cold starts. Consider:
- Upgrading to Vercel Pro for better performance
- Using Vercel Edge Functions (if applicable)
- Implementing caching strategies

### Database Connection Issues

1. Verify `DATABASE_URL` is correct
2. Check if database allows connections from Vercel IPs
3. Some databases require SSL - add `?sslmode=require` to connection string

## Monitoring and Logs

View logs in real-time:
```bash
vercel logs --follow
```

Or check the Vercel dashboard:
1. Go to your project
2. Click "Deployments"
3. Select a deployment
4. Click "Logs" or "Runtime Logs"

## Updating Your App

Simply push to GitHub:
```bash
git add .
git commit -m "Update app"
git push
```

Vercel will automatically redeploy.

## Cost Considerations

### Free Tier (Hobby)
- 100GB bandwidth/month
- 6,000 build minutes/month
- Serverless function: 100GB-hrs
- Perfect for development and small projects

### Pro Tier ($20/month per user)
- 1TB bandwidth/month
- 24,000 build minutes/month
- Better performance and support

## Additional Resources

- [Vercel Documentation](https://vercel.com/docs)
- [Vercel Python Runtime](https://vercel.com/docs/functions/serverless-functions/runtimes/python)
- [Vercel Postgres](https://vercel.com/docs/storage/vercel-postgres)
- [Environment Variables](https://vercel.com/docs/concepts/projects/environment-variables)

## Support

If you encounter issues:
1. Check Vercel documentation
2. Review deployment logs
3. Check database connectivity
4. Verify all environment variables are set

---

Good luck with your deployment! 🚀
