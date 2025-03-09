from mongoengine import (
    Document, 
    StringField, 
    DecimalField, 
    EmbeddedDocument, 
    EmbeddedDocumentListField,
    EmbeddedDocumentField,
    EmailField, 
    DateTimeField
)

class BankDetails(EmbeddedDocument):
    bank_name = StringField()
    account_number = StringField()
    ifsc_code = StringField()
    branch_name = StringField()

class ClusterDetails(EmbeddedDocument):
    cluster_name = StringField(required=True, max_length=255)
    cluster_price = DecimalField(precision=2)
    cluster_timeline = StringField(max_length=255)

class UserProfile(Document):
    user_id = StringField(required=True, unique=True)
    email = EmailField(required=True)
    username = StringField(required=True)
    created_at = DateTimeField(auto_now_add=True)
    bank_details = EmbeddedDocumentField(BankDetails)
    clusters = EmbeddedDocumentListField(ClusterDetails, default=[])

    meta = {
        'collection': 'users'
    }
