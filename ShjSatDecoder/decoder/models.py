from django.db import models

class ObsHex(models.Model):
    Obs_ID = models.AutoField(primary_key=True)
    Hex_Data = models.TextField()
    Obs_date = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=['Obs_date']),
        ]

    def __str__(self):
        return f"Obs_ID: {self.Obs_ID}, Date: {self.Obs_date}"

class ObsStatus(models.Model):
    Obs_ID = models.ForeignKey(ObsHex, on_delete=models.CASCADE)
    sensor_status = models.CharField(max_length=13)
    reset_count = models.IntegerField()
    last_reset_cause = models.IntegerField()

    class Meta:
        indexes = [
            models.Index(fields=['reset_count']),
            models.Index(fields=['last_reset_cause']),
        ]

    def __str__(self):
        return f"Obs_ID: {self.Obs_ID.Obs_ID}, Sensor Status: {self.sensor_status}"
