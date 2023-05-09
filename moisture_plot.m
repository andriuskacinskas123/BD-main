% Define Thingspeak channel and API key
readAPIKey = 'T0G73G5T98U8G70M';
channelID = 2089615;

% Define time span for the plot
startDate = datetime('2023-05-02');
endDate = datetime('now');

% Read data from Thingspeak
data = thingSpeakRead(channelID,'ReadKey',readAPIKey,'Fields',[2],'DateRange',[startDate,endDate]);

% Plot the data
plot(data,'LineWidth',2.5);

% Set y-axis limits
ylim([0,100]);

% Add title and axis labels
title('Moisture');
xlabel('Time');
ylabel('%');