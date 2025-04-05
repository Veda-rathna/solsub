from mongoengine import (
    Document, 
    StringField, 
    DecimalField, 
    EmbeddedDocument, 
    EmbeddedDocumentListField,
    EmbeddedDocumentField,
    EmailField, 
    DateTimeField,
    BooleanField,
    IntField
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
    api_key = StringField(max_length=32)
    match_id_type = StringField(default='admin_generated', choices=('admin_generated', 'user_created'))

class MatchId(Document):
    match_id = StringField(required=True, unique=True)
    cluster_name = StringField(required=True)
    timestamp = DateTimeField(required=True)
    days_valid = IntField(required=True)
    api_key = StringField(max_length=32)
    
    meta = {
        'collection': 'match_ids'
    }
    
    @classmethod
    def get_by_cluster(cls, cluster_name):
        """Get match ID for a specific cluster"""
        return cls.objects(cluster_name=cluster_name).first()
    
    @classmethod
    def is_active(cls, match_id):
        """Check if a match ID is active based on its timestamp and validity period"""
        from datetime import datetime, timedelta
        
        match = cls.objects(match_id=match_id).first()
        if not match:
            return False
            
        expiry_date = match.timestamp + timedelta(days=match.days_valid)
        return datetime.now() < expiry_date

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