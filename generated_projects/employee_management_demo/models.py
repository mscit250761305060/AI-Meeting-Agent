from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"

class Employee(Base):
    __tablename__ = 'employees'

    id = Column(Integer, primary_key=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone_number = Column(String(20))
    hire_date = Column(Date, nullable=False)
    position = Column(String(100))
    department = Column(String(100))
    salary = Column(Numeric(10, 2), nullable=False) # Added based on instruction: "Add Salary Field"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Employee(id={self.id}, name='{self.first_name} {self.last_name}')>"

# Example of how you might set up an engine and create tables (not part of the model definitions themselves)
# if __name__ == '__main__':
#     DATABASE_URL = "sqlite:///./employee_management.db"
#     engine = create_engine(DATABASE_URL)
#     Base.metadata.create_all(engine)
#     print("Database tables created!")
#
#     SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#     db = SessionLocal()
#
#     # Example usage
#     # new_user = User(username='admin', password_hash='hashed_password', email='admin@example.com')
#     # db.add(new_user)
#     # db.commit()
#     # db.refresh(new_user)
#     # print(f"Added user: {new_user}")
#
#     # new_employee = Employee(
#     #     first_name='John',
#     #     last_name='Doe',
#     #     email='john.doe@example.com',
#     #     phone_number='123-456-7890',
#     #     hire_date=datetime(2023, 1, 1).date(),
#     #     position='Software Engineer',
#     #     department='Engineering',
#     #     salary=75000.00
#     # )
#     # db.add(new_employee)
#     # db.commit()
#     # db.refresh(new_employee)
#     # print(f"Added employee: {new_employee}")
#
#     db.close()