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
    
    def add_cluster(self, cluster_data):
        """Adds a new cluster to the user's profile."""
        new_cluster = ClusterDetails(**cluster_data)
        self.clusters.append(new_cluster)
        self.save()
    
    @classmethod
    def cluster_name_exists(cls, cluster_name):
        """Check if a cluster name already exists in any user profile."""
        return cls.objects(clusters__cluster_name=cluster_name).first()

