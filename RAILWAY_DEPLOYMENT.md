# Railway Deployment Guide - Asset Management System

## Prerequisites
1. GitHub account with the Baserow repository
2. Railway account (https://railway.app)
3. Git CLI installed locally

## Step-by-Step Deployment

### 1. Connect Your Repository to Railway

```bash
# Login to Railway
railway login

# Link your project
railway link
```

### 2. Set Environment Variables in Railway

Go to your Railway project dashboard and add these variables:

```
BASEROW_BACKEND_DEBUG=off
SECRET_KEY=<generate-strong-key>
DATABASE_URL=<auto-populated-by-postgres>
REDIS_URL=<auto-populated-by-redis>
BASEROW_PLUGIN_DIR=/baserow/plugins
BASEROW_OSS_ONLY=true
```

### 3. Add Services

In Railway dashboard:
- Add **PostgreSQL** service
- Add **Redis** service
- Connect them to your Baserow service

### 4. Deploy

Option A: Auto-deploy from GitHub
```bash
# Push your branch to trigger deployment
git push origin claude/build-repo-website-2ZUGi
```

Option B: Manual deploy
```bash
railway up
```

### 5. Run Migrations

```bash
railway run python backend/src/baserow/manage.py migrate
```

### 6. Create Superuser (Optional)

```bash
railway run python backend/src/baserow/manage.py createsuperuser
```

### 7. Access Your App

Your app will be available at:
- **API:** `https://<your-railway-url>/api/`
- **Asset Management:** `https://<your-railway-url>/workspaces/{id}/assets/`

## Asset Management Endpoints

```
GET    /api/workspaces/{id}/assets/
POST   /api/workspaces/{id}/assets/
GET    /api/workspaces/{id}/assets/{asset_id}/
PUT    /api/workspaces/{id}/assets/{asset_id}/
DELETE /api/workspaces/{id}/assets/{asset_id}/

POST   /api/workspaces/{id}/assets/{id}/download/
POST   /api/workspaces/{id}/assets/{id}/upload_version/
POST   /api/workspaces/{id}/assets/{id}/rollback_version/

GET    /api/workspaces/{id}/asset-categories/
POST   /api/workspaces/{id}/asset-categories/

GET    /api/workspaces/{id}/assets/{id}/permissions/
POST   /api/workspaces/{id}/assets/{id}/permissions/grant/

GET    /api/workspaces/{id}/assets/{id}/shares/
POST   /api/workspaces/{id}/assets/{id}/shares/create_share/
```

## Features Deployed

✅ Asset upload and storage
✅ Version history and rollback
✅ Role-based permissions
✅ Shareable links with password protection
✅ Activity audit trail
✅ Categories and tags
✅ Download/view counting
✅ Complete REST API

## Troubleshooting

### Migrations fail
```bash
railway run python backend/src/baserow/manage.py migrate --fake-initial
```

### Static files not loading
```bash
railway run python backend/src/baserow/manage.py collectstatic --noinput
```

### Database connection issues
Check Railway dashboard for PostgreSQL connection string

### Worker issues (Celery)
```bash
railway run celery -A baserow.config worker -l info
```

## Important Files

- `Procfile` - Process definitions
- `railway.json` - Railway configuration
- `.railway/railway.toml` - Alternative Railway config
- `.env` - Environment variables (create from example)

## Support

For issues:
1. Check Railway dashboard logs
2. Review GitHub Actions (if using auto-deploy)
3. Check application logs: `railway logs`

## Next Steps

After deployment, you can:
1. Customize domain settings
2. Set up SSL/TLS
3. Configure backup strategies
4. Monitor application performance
5. Add team members with Railway access
