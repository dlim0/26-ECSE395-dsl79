# Known limits and next steps

- **No deer recognition:** model attempt failed the demonstration; growth heuristic accepts any suitable foreground region. Do not call this validated deer identification.
- **Fixed reference:** moving the camera, changing the scene or lighting can produce large changes. Recalibrate after moving it. Current compensation removes median brightness shift, not every exposure/shadow effect.
- **Approach assumption:** stationary, sideways, retreating, distant or rapidly entering animals may not meet the five-frame growth rule or ten-frame limit. Component overlap is a tracking heuristic and can merge/switch objects.
- **Thresholds are provisional:** 10%, 25% growth and 96-pixel gain were chosen from limited indoor evidence. A small nearby animal can look large. No field accuracy or long-duration stability statistics exist here.
- **PIR startup and hold:** warmup is 60 seconds; output must return LOW before a new HIGH. Continuous HIGH can mean hold/retrigger, nearby motion or wiring trouble. User found reversed PIR power/ground during debugging; correct supply polarity before testing.
- **Camera bus:** camera D3 must be wired to Feather D12/GPIO12. Initialization alone does not prove image data are correct; inspect decoded JPEGs. Saved images may be sideways; orientation is unchanged in current firmware.
- **RGB versus TFT:** GPIO35/36 are shared. Current firmware leaves TFT off/CS high and uses those pins for RGB. Do not enable TFT with RGB attached there. White is RGB mixing, not a calibrated photographic flash; no matched on/off test quantifies brightness gain.
- **Power:** complete battery operation was user-confirmed. No runtime/current measurements. MCU stays awake; Wi-Fi off; camera uses standby. PIR supply matches the user's tested setup; its exact final VCC header was not recorded, so confirm it on the hardware rather than guessing.
- **Buzzer hardware:** signal remains GPIO10, but it was unplugged during later tests for lack of jumpers. Firmware alarm logs do not prove physical sound. Reconnect to test sound; deterrent effectiveness against deer is unmeasured.
- **Evidence gaps:** some early recordings began after events or ended mid-window; those claims are qualified in historical notes. No outdoor observations were supplied. Model framing inputs were not independently retained.
- **Next:** repeat centered small/large trials at measured distances; include cross-traffic, shadows, foliage/wind and empty-scene controls. Document battery run duration and supply voltage. Record failures, not only successful triggers.
