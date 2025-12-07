"""
Daily Digest 历史记录数据模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path

Base = declarative_base()

class DigestHistory(Base):
    """Daily Digest 历史记录表"""
    __tablename__ = 'digest_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    
    # 摘要结果
    summary = Column(Text, nullable=True)
    post_count = Column(Integer, default=0)
    
    # 卡片信息
    ticker = Column(String(20), nullable=True)
    sentiment_score = Column(Float, nullable=True)
    sentiment_label = Column(String(50), nullable=True)
    headline = Column(String(500), nullable=True)
    key_factors = Column(Text, nullable=True)  # JSON格式存储
    
    # 热门帖子（JSON格式）
    top_posts = Column(Text, nullable=True)
    
    def to_dict(self):
        """转换为字典"""
        import json
        return {
            'id': self.id,
            'keyword': self.keyword,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'summary': self.summary,
            'post_count': self.post_count,
            'cover_card': {
                'ticker': self.ticker,
                'sentiment_score': self.sentiment_score,
                'sentiment_label': self.sentiment_label,
                'headline': self.headline,
                'key_factors': json.loads(self.key_factors) if self.key_factors else []
            },
            'top_posts': json.loads(self.top_posts) if self.top_posts else []
        }


# 数据库连接
def get_db_session():
    """获取数据库会话"""
    from dotenv import load_dotenv
    load_dotenv()
    
    # 从环境变量读取数据库配置 (优先使用项目统一的 DB_* 配置)
    db_user = os.getenv('DB_USER', os.getenv('POSTGRES_USER', 'postgres'))
    db_password = os.getenv('DB_PASSWORD', os.getenv('POSTGRES_PASSWORD', ''))
    db_host = os.getenv('DB_HOST', os.getenv('POSTGRES_HOST', 'localhost'))
    db_port = os.getenv('DB_PORT', os.getenv('POSTGRES_PORT', '5432'))
    db_name = os.getenv('DB_NAME', os.getenv('POSTGRES_DB', 'mindspider'))
    
    # 确保端口是字符串
    db_port = str(db_port)
    
    # 创建连接字符串 (使用 psycopg 3 驱动)
    database_url = f'postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    
    # 创建引擎
    engine = create_engine(database_url, echo=False)
    
    # 创建表（如果不存在）
    Base.metadata.create_all(engine)
    
    # 创建会话
    Session = sessionmaker(bind=engine)
    return Session()


def save_digest_history(keyword, result):
    """保存digest历史记录"""
    import json
    
    try:
        session = get_db_session()
        
        # 提取卡片信息
        cover_card = result.get('cover_card', {})
        
        # 创建历史记录
        history = DigestHistory(
            keyword=keyword,
            summary=result.get('summary', ''),
            post_count=result.get('post_count', 0),
            ticker=cover_card.get('ticker', keyword),
            sentiment_score=float(cover_card.get('sentiment_score', 5.0)),
            sentiment_label=cover_card.get('sentiment_label', 'N/A'),
            headline=cover_card.get('headline', ''),
            key_factors=json.dumps(cover_card.get('key_factors', []), ensure_ascii=False),
            top_posts=json.dumps(result.get('top_posts', []), ensure_ascii=False)
        )
        
        session.add(history)
        session.commit()
        
        return True, history.id
    except Exception as e:
        print(f"保存历史记录失败: {e}")
        return False, None
    finally:
        session.close()


def get_digest_history_list(limit=50):
    """获取历史记录列表"""
    try:
        session = get_db_session()
        
        # 按时间倒序查询
        histories = session.query(DigestHistory).order_by(
            DigestHistory.created_at.desc()
        ).limit(limit).all()
        
        result = []
        for h in histories:
            result.append({
                'id': h.id,
                'keyword': h.keyword,
                'created_at': h.created_at.strftime('%Y-%m-%d %H:%M'),
                'sentiment_label': h.sentiment_label,
                'post_count': h.post_count
            })
        
        return result
    except Exception as e:
        print(f"获取历史记录失败: {e}")
        return []
    finally:
        session.close()


def get_digest_by_id(history_id):
    """根据ID获取历史记录详情"""
    try:
        session = get_db_session()
        
        history = session.query(DigestHistory).filter_by(id=history_id).first()
        
        if history:
            return history.to_dict()
        return None
    except Exception as e:
        print(f"获取历史详情失败: {e}")
        return None
    finally:
        session.close()
