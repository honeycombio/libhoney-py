class SendError(Exception):
    ''' raised when send is called on an event that cannot be sent, such as:
        - when it lacks a writekey
        - dataset is not specified
        - no fields are set
    '''
    pass
