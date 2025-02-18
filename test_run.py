import os
import libhoney

libhoney.init(writekey=os.getenv('WRITEKEY'), dataset="MyCodeExerciseDataset")
libhoney.create_mark({'start_time': 1234567890, 'end_time': 1234567891, 'message': 'deploy #123', 'type': 'deploy', 'url': 'http://example.com'})