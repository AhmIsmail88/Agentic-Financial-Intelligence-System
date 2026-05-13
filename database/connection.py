from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import insert
from app.config import settings
from app.database.models import Base, Category
import logging

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.postgres_url, 
    echo=False,
    connect_args={"statement_cache_size": 0}
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db_session():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        # Create tables
        await conn.run_sync(Base.metadata.create_all)
        
    # Seed categories
    FIXED_CATEGORIES = [
        "Food", "Transport", "Utilities", "Entertainment", 
        "Electronics", "Health", "Education", "Shopping", 
        "Housing", "Other"
    ]
    
    async with AsyncSessionLocal() as session:
        for cat_name in FIXED_CATEGORIES:
            # Simple check/insert for seeding
            from sqlalchemy import select
            result = await session.execute(select(Category).where(Category.name == cat_name))
            if not result.scalar_one_or_none():
                session.add(Category(name=cat_name))
        
        await session.commit()
        logger.info("Database initialized and categories seeded.")
