from passlib.context import CryptContext

# GENERATION BCRYPT FOR HASHING USER PASSWORDS
hash_context = CryptContext(schemes=["bcrypt"], deprecated="auto")